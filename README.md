# Fama-French 3 Factor Model

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18883631.svg)](https://doi.org/10.5281/zenodo.18883631)

This code replicates the Fama-French (1993) three-factor model from scratch using WRDS data (CRSP and Compustat). It is designed to be transparent, self-contained, and ready for academic research.

---

## Background

If you're new to finance, here's the question that started it all: **why do some stocks earn higher returns than others?**

The first serious answer came from William Sharpe in the 1960s — the Capital Asset Pricing Model (CAPM). It said that a stock's expected return depends on one thing only: how sensitive it is to the overall market. If the market goes up 10% and your stock goes up 15%, your stock has a beta of 1.5, and you should expect higher returns as compensation for that extra volatility.

For a while, this was the whole story. Then the cracks started to show.

Researchers noticed that small companies consistently earned higher returns than large companies, even after adjusting for market risk. They also noticed that "value" stocks — companies trading at low prices relative to their book value — consistently beat "growth" stocks. CAPM couldn't explain either pattern.

In 1993, Eugene Fama and Kenneth French proposed a simple fix: instead of one factor, use three. Their model became the foundation of modern empirical finance. Thirty years later, it's still the first model most researchers reach for when they need to explain stock returns or evaluate portfolio performance.

---

## The Three Factors

### Mkt−RF (Market Risk Premium)

This is the oldest and most intuitive factor. The stock market, as a whole, is riskier than parking your money in Treasury bills. Investors expect to be paid for taking that risk. The market risk premium is simply the return on the broad stock market minus the risk-free rate.

When people say "the market was up 2% this month," they're talking about this factor. It captures the shared fate of all stocks — the tide that lifts or sinks every boat.

### SMB (Small Minus Big)

Small companies have historically earned higher returns than large companies. Not every year, not every decade — but on average, over long periods, the pattern is remarkably persistent.

Why? The most common explanation is straightforward: small firms are genuinely riskier. A company with $50 million in revenue and one product line is more vulnerable than Apple or Johnson & Johnson. It's harder to get a bank loan, harder to survive a recession, harder to attract top talent. Investors who hold these stocks are bearing real economic risk, and SMB is the return they earn for doing so.

The size effect was one of the first "anomalies" discovered in finance. Rolf Banz documented it in 1981, and it changed how we think about stock returns.

### HML (High Minus Low)

This factor captures the difference between "value" stocks and "growth" stocks. The distinction comes from the book-to-market ratio:

- **Book value** is what the accountants say a company is worth — its assets minus its liabilities, as reported on the balance sheet.
- **Market value** is what investors are willing to pay for it — the stock price times the number of shares.

When book value is high relative to market value (high B/M), it usually means the market is pessimistic about the company. Maybe earnings have been declining, or the industry is shrinking, or management has made mistakes. These are the "value" stocks — unloved, out of favor, often ugly.

When book value is low relative to market value (low B/M), the market is optimistic. These are the "growth" stocks — the ones with exciting stories, rapid revenue growth, and high expectations baked into the price.

Here's the puzzle: the ugly stocks, on average, outperform the exciting ones. Fama and French documented this in 1992 and built it into their model a year later. The debate about *why* this happens — risk or mispricing — continues to this day.

---

## How the Portfolios Are Constructed

The elegance of the Fama-French approach is in its simplicity. But the details matter enormously. Small deviations from the methodology can produce factors that diverge significantly from the official ones.

### Step 1: Gather the data

Every June, we need two pieces of information for each stock:
- **Market equity (ME):** the stock price times shares outstanding, as of June 30.
- **Book equity (BE):** from the most recent fiscal year financial statements, subject to a six-month lag.

The six-month lag is critical. A company's December 2022 financial statements aren't publicly available until sometime in early 2023 — often March or April. If we used that data in January 2023, we'd be using information that real investors didn't have. That's look-ahead bias, and it invalidates any backtest. By waiting until June, we're confident the data was public.

### Step 2: Compute Book-to-Market

B/M = Book Equity / Market Equity. We use fiscal year-end book equity (with the lag described above) divided by June market equity. Stocks with negative book equity are excluded — they're economically meaningless for this purpose.

### Step 3: Set breakpoints using NYSE stocks only

This is a subtle but important point. We compute the size breakpoint (median market cap) and B/M breakpoints (30th and 70th percentiles) using **only NYSE-listed stocks**. Why? Because NASDAQ is full of tiny stocks. If we used all stocks to set breakpoints, the "small" group would contain thousands of micro-caps and the "big" group would be oddly small. NYSE breakpoints produce a more balanced and economically meaningful split.

### Step 4: Sort all stocks into 2×3 portfolios

Using the NYSE breakpoints, we classify **every stock** (NYSE, AMEX, and NASDAQ) into one of six portfolios:

|  | Low B/M (Growth) | Medium B/M | High B/M (Value) |
|--|-------------------|------------|-------------------|
| **Small** | SL | SM | SH |
| **Big** | BL | BM | BH |

### Step 5: Compute monthly returns

From July of year t through June of year t+1, we compute the **value-weighted** return of each portfolio every month. Value-weighted means that larger stocks within each portfolio have more influence on the portfolio return — just like in a market index.

### Step 6: Compute the factors

```
SMB = (SL + SM + SH) / 3  −  (BL + BM + BH) / 3
HML = (SH + BH) / 2  −  (SL + BL) / 2
Mkt−RF = Value-weighted market return  −  Risk-free rate
```

---

## What the Code Does

The implementation is a single Python file (`main.py`) with a clear, linear pipeline. Here's what each stage does:

### Stage 1: CRSP Download

Pulls monthly data from the CRSP stock file. For each stock-month, we get the return, price, shares outstanding (to compute market cap), exchange code, and SIC industry code.

Key filters:
- **Common stock only** (share codes 10 and 11) — this excludes ADRs, REITs, closed-end funds, and other non-standard securities that don't belong in the Fama-French universe.
- **NYSE, AMEX, NASDAQ only** (exchange codes 1, 2, 3).
- **Financial firms excluded** (SIC 6000–6999) — banks, insurance companies, and broker-dealers have fundamentally different balance sheets. Their book equity isn't comparable to industrial firms.
- **Delisting return adjustment** — when a stock is delisted (due to bankruptcy, merger, etc.), CRSP records a final "delisting return" in a separate table. If you ignore this, you systematically miss the large negative returns of firms that go bankrupt, creating survivorship bias. The code merges delisting returns into the regular return series: adjusted return = (1 + ret) × (1 + dlret) − 1.

Market equity is computed as |price| × shares outstanding / 1000, giving us millions of dollars (CRSP stores shares in thousands).

### Stage 2: Compustat Download

Pulls annual accounting data from Compustat's Fundamentals Annual file. The key variable is **book equity**, computed following Davis, Fama, and French (2000):

```
Stockholders' Equity (SE):
  → Use SEQ if available
  → Otherwise: CEQ + PSTK
  → Otherwise: AT − LT (total assets minus total liabilities)

Preferred Stock (PS):
  → Use PSTKRV (redemption value) if available
  → Otherwise: PSTKL (liquidating value)
  → Otherwise: PSTK (par value)
  → Otherwise: 0

Book Equity = SE + TXDITC (deferred taxes) − PS
```

This hierarchy matters. Different firms report different items, and the fallback logic ensures we lose as few observations as possible while maintaining accuracy.

The code accepts **all fiscal year ends**, not just December. About 70-80% of U.S. firms have December fiscal years, but restricting to December would unnecessarily discard the rest.

### Stage 3: CRSP-Compustat Link

The two databases use different identifiers — CRSP uses PERMNO, Compustat uses GVKEY. The CCM (CRSP-Compustat Merged) link table maps between them. The code respects link validity dates and prioritizes primary links over secondary ones.

### Stage 4: June Portfolio Formation

For each June, the code:
1. Takes each stock's June market cap from CRSP.
2. Finds the most recent Compustat book equity where the fiscal year ended **on or before December 31 of the prior year** (the six-month lag rule).
3. Computes B/M = BE / ME.
4. Winsorizes B/M at the 1st and 99th percentiles to limit the influence of extreme outliers.
5. Computes NYSE breakpoints and assigns every stock to one of six portfolios.

### Stage 5: Monthly Factor Returns

For each month from July through the following June:
1. Maps each stock to its portfolio assignment (from the most recent June).
2. Computes value-weighted portfolio returns using **lagged market cap** (end of prior month) as weights — this avoids the mechanical correlation between current returns and current market cap.
3. Computes SMB, HML, and Mkt−RF.

### Stage 6: Risk-Free Rate

The risk-free rate comes from Kenneth French's data library (the most authoritative source). If that's unavailable, the code falls back to the CRSP 1-month T-Bill return.

### Stage 7: Output

Saves monthly factors to `output/ff3_factors.csv` with columns: `date`, `mkt_rf`, `smb`, `hml`, `rf`.

---

## Getting Started

You need a WRDS account (most universities provide institutional access).

```bash
pip install wrds pandas numpy pandas-datareader

cp env_example.txt .env
# Open .env and enter your WRDS username and password

python main.py --start 2000-07-01 --end 2023-12-31
```

The `.env` file keeps your credentials out of the code. Never share it or upload it.

---

## References

- Fama, E.F. and French, K.R. (1993). "Common risk factors in the returns on stocks and bonds." *Journal of Financial Economics*, 33(1), 3-56.
- Davis, J.L., Fama, E.F. and French, K.R. (2000). "Characteristics, Covariances, and Average Returns: 1929 to 1997." *Journal of Finance*, 55(1), 389-406.
- Banz, R.W. (1981). "The relationship between return and market value of common stocks." *Journal of Financial Economics*, 9(1), 3-18.
- Kenneth French's Data Library: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html

### Citation

```bibtex
@software{jihwanw_ff3,
  author    = {jihwanw},
  title     = {Fama-French 3 Factor Model},
  year      = {2026},
  publisher = {GitHub},
  url       = {https://github.com/jihwanw/fama-french-3factor},
  doi       = {10.5281/zenodo.18883631}
}
```

---

---

# 한국어 설명

## 배경

재무금융을 처음 접하는 분이라면, 이 질문에서 시작하면 됩니다. **왜 어떤 주식은 다른 주식보다 수익률이 높은가?**

최초의 본격적인 답은 1960년대 William Sharpe의 CAPM이었습니다. 주식의 기대수익률은 시장 전체와 얼마나 같이 움직이느냐에 달려 있다는 이론이었죠. 시장이 10% 오를 때 15% 오르는 주식은 베타가 1.5이고, 그만큼 높은 수익률을 기대할 수 있다는 것입니다.

한동안 이것이 전부였습니다. 그러다 균열이 생기기 시작했습니다.

연구자들이 발견한 것은, 시장 위험을 보정한 후에도 소형주가 대형주보다 꾸준히 높은 수익률을 기록한다는 것이었습니다. 또한 장부가 대비 시가가 높은 "가치주"가 낮은 "성장주"를 꾸준히 이긴다는 것도 발견했습니다. CAPM으로는 어느 쪽도 설명할 수 없었습니다.

1993년, Fama와 French가 간단한 해법을 제시했습니다. 팩터를 하나가 아니라 세 개 쓰자는 것이었습니다. 이 모델은 현대 실증 재무금융의 토대가 되었고, 30년이 지난 지금도 연구자들이 주식 수익률을 설명하거나 포트폴리오 성과를 평가할 때 가장 먼저 꺼내는 도구입니다.

---

## 3가지 팩터

### Mkt−RF (시장 위험 프리미엄)

가장 오래되고 직관적인 팩터입니다. 주식시장 전체는 국채에 돈을 넣어두는 것보다 위험합니다. 투자자들은 그 위험을 감수하는 대가를 기대합니다. 시장 위험 프리미엄은 단순히 전체 주식시장 수익률에서 무위험수익률을 뺀 것입니다.

"이번 달 시장이 2% 올랐다"고 할 때, 바로 이 팩터를 말하는 것입니다. 모든 주식의 공통된 운명 — 밀물이 오면 모든 배가 뜨고, 썰물이 오면 모든 배가 가라앉는 것 — 을 포착합니다.

### SMB (소형주 − 대형주)

소형주가 역사적으로 대형주보다 높은 수익률을 기록해왔습니다. 매년 그런 것은 아니고, 매 10년 그런 것도 아닙니다. 하지만 장기 평균으로 보면 패턴은 놀라울 정도로 일관됩니다.

왜일까요? 가장 흔한 설명은 단순합니다. 소형주가 진짜로 더 위험하기 때문입니다. 매출 500억에 제품 하나인 회사는 삼성전자나 존슨앤존슨보다 취약합니다. 은행 대출 받기도 어렵고, 불황을 버티기도 어렵고, 인재를 끌어오기도 어렵습니다. 이런 주식을 보유하는 투자자는 실질적인 경제적 위험을 감수하는 것이고, SMB는 그 대가입니다.

규모 효과는 재무금융에서 최초로 발견된 "이상현상" 중 하나입니다. Rolf Banz가 1981년에 이를 기록했고, 주식 수익률에 대한 우리의 사고방식을 바꿔놓았습니다.

### HML (가치주 − 성장주)

이 팩터는 "가치주"와 "성장주"의 수익률 차이를 포착합니다. 구분의 기준은 장부가 대 시가 비율입니다:

- **장부가치**는 회계사가 말하는 기업의 가치입니다 — 대차대조표에 기록된 자산에서 부채를 뺀 것.
- **시장가치**는 투자자들이 기꺼이 지불하려는 가격입니다 — 주가 곱하기 발행주식수.

장부가치가 시장가치에 비해 높으면(높은 B/M), 보통 시장이 그 기업에 대해 비관적이라는 뜻입니다. 실적이 하락하고 있거나, 산업이 축소되고 있거나, 경영진이 실수를 했을 수 있습니다. 이것이 "가치주"입니다 — 사랑받지 못하고, 외면당하고, 대개 볼품없는 주식들.

장부가치가 시장가치에 비해 낮으면(낮은 B/M), 시장이 낙관적이라는 뜻입니다. 이것이 "성장주"입니다 — 흥미진진한 스토리, 빠른 매출 성장, 높은 기대가 가격에 반영된 주식들.

퍼즐은 이것입니다: 볼품없는 주식이, 평균적으로, 흥미진진한 주식을 이깁니다. Fama와 French가 1992년에 이를 기록하고 1년 후 모델에 반영했습니다. *왜* 이런 일이 일어나는지 — 위험 때문인지 잘못된 가격 때문인지 — 에 대한 논쟁은 오늘날까지 계속되고 있습니다.

---

## 포트폴리오 구성 방법

Fama-French 방법론의 매력은 단순함에 있습니다. 하지만 세부사항이 대단히 중요합니다. 방법론에서 조금만 벗어나도 공식 팩터와 크게 다른 결과가 나옵니다.

### 1단계: 데이터 수집

매년 6월, 각 주식에 대해 두 가지 정보가 필요합니다:
- **시장가치(ME):** 6월 30일 기준 주가 × 발행주식수
- **장부가치(BE):** 가장 최근 회계연도 재무제표에서, 최소 6개월 지연 적용

6개월 지연이 핵심입니다. 2022년 12월 재무제표는 2023년 초 — 보통 3~4월 — 에야 공개됩니다. 2023년 1월에 그 데이터를 쓰면 실제 투자자가 갖고 있지 않았던 정보를 사용하는 것입니다. 이것이 미래정보 편향이고, 모든 백테스트를 무효화합니다. 6월까지 기다리면 데이터가 공개된 후라는 것을 확신할 수 있습니다.

### 2단계: B/M 계산

B/M = 장부가치 / 시장가치. 음수 장부가치는 제외합니다.

### 3단계: NYSE 주식만으로 기준점 설정

미묘하지만 중요한 점입니다. 규모 기준점(시가총액 중앙값)과 B/M 기준점(30%, 70% 백분위수)은 **NYSE 상장 주식만**으로 계산합니다. NASDAQ에는 아주 작은 주식이 많기 때문입니다. 전체 주식으로 기준점을 잡으면 "소형" 그룹에 수천 개의 초소형주가 들어가고 "대형" 그룹은 이상하게 작아집니다.

### 4단계: 모든 주식을 2×3 포트폴리오로 분류

NYSE 기준점을 사용하여 **모든 주식**(NYSE, AMEX, NASDAQ)을 6개 포트폴리오 중 하나로 분류합니다.

### 5단계: 월별 수익률 계산

t년 7월부터 t+1년 6월까지, 매월 각 포트폴리오의 **시가총액 가중** 수익률을 계산합니다.

### 6단계: 팩터 계산

```
SMB = (SL + SM + SH) / 3  −  (BL + BM + BH) / 3
HML = (SH + BH) / 2  −  (SL + BL) / 2
Mkt−RF = 시가총액 가중 시장수익률  −  무위험수익률
```

---

## 코드가 하는 일

구현은 단일 Python 파일(`main.py`)이며, 명확한 파이프라인으로 구성되어 있습니다.

### 1단계: CRSP 다운로드

CRSP 월별 주식 파일에서 데이터를 가져옵니다. 각 주식-월에 대해 수익률, 가격, 발행주식수(시가총액 계산용), 거래소 코드, SIC 산업 코드를 가져옵니다.

핵심 필터:
- **보통주만** (share code 10, 11) — ADR, REIT, 폐쇄형 펀드 등 Fama-French 유니버스에 속하지 않는 증권을 제외합니다.
- **NYSE, AMEX, NASDAQ만** (거래소 코드 1, 2, 3).
- **금융업 제외** (SIC 6000-6999) — 은행, 보험사, 증권사는 대차대조표 구조가 근본적으로 다릅니다. 장부가치를 산업체와 비교할 수 없습니다.
- **상장폐지 수익률 보정** — 주식이 상장폐지되면(파산, 합병 등) CRSP가 별도 테이블에 최종 수익률을 기록합니다. 이를 무시하면 파산 기업의 큰 음의 수익률을 체계적으로 놓치게 되어 생존편향이 발생합니다. 코드는 상장폐지 수익률을 일반 수익률에 합산합니다: 보정 수익률 = (1 + ret) × (1 + dlret) − 1.

시가총액은 |가격| × 발행주식수 / 1000으로 계산하여 백만달러 단위입니다 (CRSP는 주식수를 천주 단위로 저장).

### 2단계: Compustat 다운로드

Compustat 연간 재무 파일에서 회계 데이터를 가져옵니다. 핵심 변수는 **장부가치**이며, Davis, Fama, French (2000) 정의를 따릅니다:

```
주주자본(SE):
  → SEQ가 있으면 사용
  → 없으면: CEQ + PSTK
  → 없으면: AT − LT (총자산 − 총부채)

우선주(PS):
  → PSTKRV (상환가치) 우선
  → 없으면: PSTKL (청산가치)
  → 없으면: PSTK (액면가)
  → 없으면: 0

장부가치 = SE + TXDITC (이연법인세) − PS
```

이 우선순위가 중요합니다. 기업마다 보고하는 항목이 다르고, fallback 로직이 있어야 정확성을 유지하면서 관측치 손실을 최소화할 수 있습니다.

코드는 12월 결산뿐 아니라 **모든 회계연도 말**을 허용합니다. 미국 기업의 약 70-80%가 12월 결산이지만, 12월로 제한하면 나머지를 불필요하게 버리게 됩니다.

### 3단계: CRSP-Compustat 연결

두 데이터베이스는 다른 식별자를 사용합니다 — CRSP는 PERMNO, Compustat는 GVKEY. CCM 링크 테이블이 둘을 연결합니다. 코드는 링크 유효기간을 확인하고 Primary 링크를 우선합니다.

### 4단계: 6월 포트폴리오 구성

매년 6월, 코드는:
1. CRSP에서 각 주식의 6월 시가총액을 가져옵니다.
2. 회계연도가 **전년 12월 31일 이전에 끝난** 가장 최근 Compustat 장부가치를 찾습니다 (6개월 lag 규칙).
3. B/M = BE / ME를 계산합니다.
4. B/M을 1%, 99% 백분위수에서 winsorize하여 극단값의 영향을 제한합니다.
5. NYSE 기준점을 계산하고 모든 주식을 6개 포트폴리오에 배정합니다.

### 5단계: 월별 팩터 수익률

7월부터 다음해 6월까지 매월:
1. 각 주식을 가장 최근 6월의 포트폴리오 배정에 매핑합니다.
2. **전월 말 시가총액**을 가중치로 사용하여 시가총액 가중 포트폴리오 수익률을 계산합니다 — 당월 수익률과 당월 시가총액 사이의 기계적 상관을 피하기 위해서입니다.
3. SMB, HML, Mkt−RF를 계산합니다.

### 6단계: 무위험수익률

무위험수익률은 Kenneth French 데이터 라이브러리에서 가져옵니다 (가장 권위 있는 출처). 접속이 안 되면 CRSP 1개월 T-Bill 수익률로 대체합니다.

### 7단계: 출력

월별 팩터 수익률을 `output/ff3_factors.csv`에 저장합니다. 컬럼: `date`, `mkt_rf`, `smb`, `hml`, `rf`.

---

## 실행 방법

WRDS 계정이 필요합니다 (대부분의 대학에서 기관 접근권을 제공합니다).

```bash
pip install wrds pandas numpy pandas-datareader

cp env_example.txt .env
# .env 파일을 열고 WRDS 사용자명과 비밀번호를 입력하세요

python main.py --start 2000-07-01 --end 2023-12-31
```

`.env` 파일은 인증 정보를 코드 밖에 보관합니다. 절대 공유하거나 업로드하지 마세요.

---

## 참고문헌

- Fama, E.F. and French, K.R. (1993). "Common risk factors in the returns on stocks and bonds." *Journal of Financial Economics*, 33(1), 3-56.
- Davis, J.L., Fama, E.F. and French, K.R. (2000). "Characteristics, Covariances, and Average Returns: 1929 to 1997." *Journal of Finance*, 55(1), 389-406.
- Banz, R.W. (1981). "The relationship between return and market value of common stocks." *Journal of Financial Economics*, 9(1), 3-18.
- Kenneth French's Data Library: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html

### 인용

```bibtex
@software{jihwanw_ff3,
  author    = {jihwanw},
  title     = {Fama-French 3 Factor Model},
  year      = {2026},
  publisher = {GitHub},
  url       = {https://github.com/jihwanw/fama-french-3factor},
  doi       = {10.5281/zenodo.18883631}
}
```
