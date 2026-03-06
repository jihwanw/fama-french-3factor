"""
Fama-French 3 Factor Model — 완전한 구현
=========================================
Davis, Fama, and French (2000) 방법론 준수

사용법:
  1. .env 파일에 WRDS_USERNAME, WRDS_PASSWORD 설정
  2. python main.py --start 2000-07-01 --end 2023-12-31

단위:
  CRSP:     prc=달러, shrout=천주 → ME = abs(prc)*shrout/1000 = 백만달러
  Compustat: 모든 금액 = 백만달러
  B/M = BE(백만달러) / ME(백만달러)
"""

import os
import argparse
import pandas as pd
import numpy as np
import wrds
import warnings
warnings.filterwarnings('ignore')


def _load_credentials():
    """
    .env 파일에서 WRDS 인증 정보 로드.
    환경변수가 이미 설정되어 있으면 그것을 우선 사용.
    """
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())

    username = os.environ.get('WRDS_USERNAME')
    password = os.environ.get('WRDS_PASSWORD')
    if not username or not password:
        raise ValueError(
            "WRDS 인증 정보가 없습니다.\n"
            ".env 파일에 WRDS_USERNAME, WRDS_PASSWORD를 설정하거나\n"
            "환경변수로 export 해주세요."
        )
    return username, password


# ─────────────────────────────────────────────────────
# WRDS 데이터 다운로드
# ─────────────────────────────────────────────────────

def connect_wrds():
    _load_credentials()
    db = wrds.Connection(
        wrds_username=os.environ['WRDS_USERNAME'],
        wrds_password=os.environ['WRDS_PASSWORD'],
    )
    print("✅ WRDS 연결 성공")
    return db


def download_crsp(db, start, end):
    """
    CRSP 월별 데이터. 보통주(shrcd 10,11), 금융업 제외, 델리스팅 보정.
    """
    q = f"""
    SELECT a.permno, a.date, a.ret,
           ABS(a.prc) * a.shrout / 1000 AS me,
           b.exchcd, b.shrcd, b.siccd,
           c.dlret
    FROM crsp.msf a
    INNER JOIN crsp.msenames b
      ON a.permno = b.permno
     AND b.namedt <= a.date AND a.date <= b.nameenddt
    LEFT JOIN crsp.msedelist c
      ON a.permno = c.permno
     AND DATE_TRUNC('month', a.date) = DATE_TRUNC('month', c.dlstdt)
    WHERE a.date BETWEEN '{start}' AND '{end}'
      AND b.shrcd IN (10, 11)
      AND b.exchcd IN (1, 2, 3)
      AND a.prc IS NOT NULL
      AND a.shrout IS NOT NULL
    """
    df = db.raw_sql(q)
    df['date'] = pd.to_datetime(df['date'])

    # 델리스팅 수익률 보정
    if 'dlret' in df.columns:
        both_null = df['ret'].isna() & df['dlret'].isna()
        df = df[~both_null].copy()
        df['ret'] = df['ret'].fillna(0)
        df['dlret'] = df['dlret'].fillna(0)
        df['ret'] = (1 + df['ret']) * (1 + df['dlret']) - 1

    df = df[df['ret'].notna()].copy()
    df = df[~df['siccd'].between(6000, 6999)].copy()
    print(f"  CRSP: {len(df):,} obs, {df['permno'].nunique():,} permnos")
    return df


def download_compustat(db, start, end):
    """
    Compustat 연간 데이터. 모든 fiscal year end 허용.
    BE = SE + TXDITC - PS  (Davis, Fama, French 2000)
    """
    q = f"""
    SELECT gvkey, datadate, fyear,
           seq, ceq, pstk, pstkrv, pstkl, txditc, at, lt
    FROM comp.funda
    WHERE datadate BETWEEN '{start}' AND '{end}'
      AND indfmt = 'INDL' AND datafmt = 'STD'
      AND popsrc = 'D'   AND consol = 'C'
    """
    df = db.raw_sql(q)
    df['datadate'] = pd.to_datetime(df['datadate'])

    # SE: seq → ceq+pstk → at-lt
    se = df['seq'].copy()
    mask1 = se.isna()
    if mask1.any():
        ceq_fill = df.loc[mask1, 'ceq'].fillna(0) + df.loc[mask1, 'pstk'].fillna(0)
        se.loc[mask1 & df['ceq'].notna()] = ceq_fill[df.loc[mask1, 'ceq'].notna()]
    mask2 = se.isna()
    if mask2.any():
        se[mask2] = df.loc[mask2, 'at'].fillna(0) - df.loc[mask2, 'lt'].fillna(0)

    ps = df['pstkrv'].fillna(df['pstkl']).fillna(df['pstk']).fillna(0)
    df['be'] = se + df['txditc'].fillna(0) - ps

    df = df[df['be'] > 0].copy()
    df['year'] = df['datadate'].dt.year
    df = df.sort_values('datadate').drop_duplicates(subset=['gvkey', 'year'], keep='last')

    print(f"  Compustat: {len(df):,} firm-years, {df['gvkey'].nunique():,} firms")
    return df[['gvkey', 'year', 'be', 'datadate']]


def download_ccm_link(db):
    """CRSP-Compustat 링크. Primary link 우선."""
    q = """
    SELECT gvkey, lpermno AS permno, linkdt, linkenddt, linkprim
    FROM crsp.ccmxpf_linktable
    WHERE linktype IN ('LU','LC') AND linkprim IN ('P','C')
    """
    lk = db.raw_sql(q)
    lk['linkdt'] = pd.to_datetime(lk['linkdt'])
    lk['linkenddt'] = pd.to_datetime(lk['linkenddt']).fillna(pd.Timestamp('2099-12-31'))
    lk['_p'] = lk['linkprim'].map({'P': 0, 'C': 1})
    lk = lk.sort_values('_p').drop_duplicates(subset=['permno', 'gvkey'], keep='first')
    print(f"  CCM Link: {len(lk):,} links")
    return lk[['gvkey', 'permno', 'linkdt', 'linkenddt']]


def download_rf(db, output_dir):
    """Kenneth French 사이트에서 RF. 실패 시 CRSP T-Bill."""
    try:
        import pandas_datareader.data as web
        ff = web.DataReader('F-F_Research_Data_Factors', 'famafrench', start='1926')[0]
        rf = ff['RF'] / 100
        rf.index = rf.index.to_timestamp()
        print("  ✅ Kenneth French RF 다운로드 완료")
        return rf
    except Exception:
        pass

    try:
        q = "SELECT caldt AS date, t30ret AS rf FROM crsp.mcti"
        rf_crsp = db.raw_sql(q)
        rf_crsp['date'] = pd.to_datetime(rf_crsp['date'])
        rf_crsp = rf_crsp.set_index('date')['rf']
        print("  ✅ CRSP T-Bill RF 다운로드 완료")
        return rf_crsp
    except Exception:
        print("  ⚠️ RF 다운로드 실패, 0 사용")
        return None


# ─────────────────────────────────────────────────────
# 포트폴리오 구성 & 팩터 계산
# ─────────────────────────────────────────────────────

def build_june_data(crsp, comp, link):
    """
    매년 6월 말: ME(t,Jun), BE(가장 최신, datadate ≤ t-1년 12월), B/M
    """
    june = crsp[crsp['date'].dt.month == 6].copy()
    june['year'] = june['date'].dt.year
    june = june.sort_values('date').drop_duplicates(subset=['permno', 'year'], keep='last')

    merged = june.merge(link, on='permno', how='inner')
    merged = merged[(merged['date'] >= merged['linkdt']) &
                    (merged['date'] <= merged['linkenddt'])].copy()

    merged['be_deadline'] = pd.to_datetime((merged['year'] - 1).astype(str) + '-12-31')
    merged = merged.merge(comp, on='gvkey', how='inner', suffixes=('', '_comp'))
    merged = merged[merged['datadate'] <= merged['be_deadline']].copy()
    merged = merged.sort_values('datadate').drop_duplicates(subset=['permno', 'year'], keep='last')

    merged['bm'] = merged['be'] / merged['me']
    merged = merged[(merged['me'] > 0) & (merged['bm'] > 0) &
                    merged['bm'].notna() & np.isfinite(merged['bm'])].copy()

    lo, hi = merged['bm'].quantile(0.01), merged['bm'].quantile(0.99)
    merged['bm'] = merged['bm'].clip(lo, hi)
    merged = merged.drop_duplicates(subset=['permno', 'year'], keep='first')

    print(f"  June data: {len(merged):,} stock-years")
    return merged[['permno', 'year', 'me', 'bm', 'exchcd']]


def form_portfolios(june_year):
    """NYSE breakpoints → 2x3 포트폴리오. 반환: {permno: label}"""
    nyse = june_year[june_year['exchcd'] == 1]
    if len(nyse) < 30:
        return None

    size_med = nyse['me'].median()
    bm_30, bm_70 = nyse['bm'].quantile(0.3), nyse['bm'].quantile(0.7)

    def classify(row):
        s = 'S' if row['me'] <= size_med else 'B'
        b = 'L' if row['bm'] <= bm_30 else ('H' if row['bm'] > bm_70 else 'M')
        return s + b

    jy = june_year.copy()
    jy['port'] = jy.apply(classify, axis=1)
    return dict(zip(jy['permno'], jy['port']))


def calculate_factors(crsp, june_all, rf_series, start, end):
    """월별 Mkt-RF, SMB, HML 계산."""
    crsp = crsp.sort_values(['permno', 'date']).copy()
    crsp['me_lag'] = crsp.groupby('permno')['me'].shift(1)

    # 연도별 포트폴리오 매핑
    port_maps = {}
    for yr in sorted(june_all['year'].unique()):
        pm = form_portfolios(june_all[june_all['year'] == yr])
        if pm:
            port_maps[yr] = pm
            counts = pd.Series(pm.values()).value_counts().sort_index()
            print(f"  {yr}년 6월: {len(pm)} 종목 | {dict(counts)}")

    results = []
    for dt in pd.date_range(start, end, freq='M'):
        yr, mo = dt.year, dt.month
        port_year = yr if mo >= 7 else yr - 1

        if port_year not in port_maps:
            continue

        mdata = crsp[(crsp['date'].dt.year == yr) & (crsp['date'].dt.month == mo)].copy()
        if len(mdata) == 0:
            continue

        # 시장수익률 (시가총액 가중, t-1월 말 ME)
        valid = mdata[(mdata['ret'].notna()) & (mdata['me_lag'] > 0)]
        if len(valid) == 0:
            continue
        mkt_ret = np.average(valid['ret'], weights=valid['me_lag'])

        # 포트폴리오 수익률 (시가총액 가중)
        mdata['port'] = mdata['permno'].map(port_maps[port_year])
        mdata = mdata[mdata['port'].notna() & mdata['ret'].notna() & (mdata['me_lag'] > 0)]
        port_ret = mdata.groupby('port').apply(lambda g: np.average(g['ret'], weights=g['me_lag']))

        required = ['SL', 'SM', 'SH', 'BL', 'BM', 'BH']
        if not all(p in port_ret.index for p in required):
            continue

        smb = (port_ret['SL'] + port_ret['SM'] + port_ret['SH']) / 3 \
            - (port_ret['BL'] + port_ret['BM'] + port_ret['BH']) / 3
        hml = (port_ret['SH'] + port_ret['BH']) / 2 \
            - (port_ret['SL'] + port_ret['BL']) / 2

        results.append({'date': dt, 'mkt_ret': mkt_ret, 'smb': smb, 'hml': hml})

    if not results:
        return None

    factors = pd.DataFrame(results)

    # RF 매칭
    factors['rf'] = 0.0
    if rf_series is not None:
        rf_map = rf_series.copy()
        rf_map.index = rf_map.index.to_period('M')
        factors['_ym'] = factors['date'].dt.to_period('M')
        factors['rf'] = factors['_ym'].map(rf_map).fillna(0)
        factors = factors.drop(columns='_ym')

    factors['mkt_rf'] = factors['mkt_ret'] - factors['rf']
    return factors[['date', 'mkt_rf', 'smb', 'hml', 'rf']]


# ─────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Fama-French 3 Factor Model')
    parser.add_argument('--start', default='2000-07-01', help='시작일 (YYYY-MM-DD)')
    parser.add_argument('--end', default='2023-12-31', help='종료일 (YYYY-MM-DD)')
    args = parser.parse_args()

    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("Fama-French 3 Factor Model")
    print("=" * 60)

    db = connect_wrds()
    try:
        data_start = (pd.to_datetime(args.start) - pd.DateOffset(years=2)).strftime('%Y-%m-%d')

        print("\n[1] 데이터 다운로드")
        crsp = download_crsp(db, data_start, args.end)
        comp = download_compustat(db, data_start, args.end)
        link = download_ccm_link(db)
        rf = download_rf(db, output_dir)

        print("\n[2] 6월 포트폴리오 구성 데이터")
        june_all = build_june_data(crsp, comp, link)

        print("\n[3] 월별 팩터 계산")
        factors = calculate_factors(crsp, june_all, rf, args.start, args.end)

        if factors is not None:
            out_path = os.path.join(output_dir, 'ff3_factors.csv')
            factors.to_csv(out_path, index=False)

            print(f"\n{'='*60}")
            print(f"✅ 완료: {len(factors)} 개월")
            print(f"  Mkt-RF: {factors['mkt_rf'].mean()*100:.2f}% (월평균)")
            print(f"  SMB:    {factors['smb'].mean()*100:.2f}%")
            print(f"  HML:    {factors['hml'].mean()*100:.2f}%")
            print(f"  저장: {out_path}")
            print(f"{'='*60}")
        else:
            print("❌ 팩터 계산 실패")
    finally:
        db.close()


if __name__ == '__main__':
    main()
