# Fama-French 3 Factor Model

> A complete, academically rigorous implementation of the Fama-French (1993) three-factor model using WRDS (CRSP + Compustat) data.

---

## Table of Contents / 목차

- [What is the Fama-French 3 Factor Model?](#what-is-the-fama-french-3-factor-model)
- [The Three Factors Explained](#the-three-factors-explained)
- [How Portfolios Are Constructed](#how-portfolios-are-constructed)
- [Implementation Details](#implementation-details)
- [Quick Start](#quick-start)
- [한국어 설명](#한국어-설명)

---

## What is the Fama-French 3 Factor Model?

In 1993, Eugene Fama and Kenneth French published a landmark paper showing that **stock returns can be explained by three factors**, not just one (the market). Before their work, the dominant model was the Capital Asset Pricing Model (CAPM), which says:

```
E(R) = RF + β × (Market Return − RF)
```

Fama and French showed this was incomplete. Small stocks and value stocks (high book-to-market) consistently earned higher returns than CAPM predicted. They proposed:

```
E(R) = RF + β₁×(Mkt−RF) + β₂×SMB + β₃×HML
```

This model has become **the standard benchmark** in academic finance for evaluating portfolio performance, testing asset pricing theories, and measuring abnormal returns (alpha).

### Why does this matter?

- If you run a hedge fund and your returns can be fully explained by these three factors, you're not generating "alpha" — you're just taking on known risk exposures.
- If a stock's return **cannot** be explained by these factors, that's interesting — it suggests mispricing or an additional risk factor.

---

## The Three Factors Explained

### 1. Market Risk Premium (Mkt−RF)

**What it is:** The return of the entire stock market minus the risk-free rate (1-month T-Bill).

**Intuition:** Stocks are riskier than government bonds, so investors demand a premium for holding them. This is the most basic and well-known factor.

**How we calculate it:**
```
Mkt−RF = Value-weighted return of all stocks − 1-month T-Bill rate
```
"Value-weighted" means larger companies have more influence on the average. Apple matters more than a tiny biotech firm.

---

### 2. SMB (Small Minus Big)

**What it is:** The return difference between small-cap and large-cap stocks.

**Intuition:** Historically, small companies have earned higher returns than large companies. Why? Possible explanations include:
- Small firms are riskier (less diversified, more volatile)
- Small firms are less liquid (harder to trade)
- Small firms have higher information asymmetry

**How we calculate it:**
```
SMB = Average return of 3 small portfolios − Average return of 3 big portfolios
    = (SL + SM + SH)/3 − (BL + BM + BH)/3
```

---

### 3. HML (High Minus Low)

**What it is:** The return difference between value stocks (high book-to-market) and growth stocks (low book-to-market).

**Intuition:** "Value stocks" are companies whose market price is low relative to their book value — the market is pessimistic about them. Historically, these stocks have outperformed "growth stocks" (glamorous, expensive companies). Why?
- Value firms may be in financial distress (higher risk → higher return)
- The market may systematically overreact to bad news

**Book-to-Market ratio:**
```
B/M = Book Equity / Market Equity
```
- **High B/M** → Value stock (cheap, out of favor)
- **Low B/M** → Growth stock (expensive, popular)

**How we calculate it:**
```
HML = Average return of 2 high-B/M portfolios − Average return of 2 low-B/M portfolios
    = (SH + BH)/2 − (SL + BL)/2
```

---

## How Portfolios Are Constructed

This is where the methodology gets precise. Every detail matters for replication.

### Timeline

```
December year t-1:  Book Equity (BE) is measured from financial statements
June year t:        Portfolios are formed using BE(t-1,Dec) / ME(t,Jun)
July year t → June year t+1:  Monthly returns are calculated for each portfolio
June year t+1:      Portfolios are reformed (annual rebalancing)
```

### Why the 6-month lag?

Financial statements for fiscal year ending December 2022 are typically not publicly available until March-April 2023. By using them in June 2023, we ensure the information was **actually available** to investors. This avoids **look-ahead bias**.

### The 2×3 Sorting Procedure

**Step 1: Size sort**
- Use the **NYSE median** market cap as the breakpoint
- Stocks below the median → **Small (S)**
- Stocks above the median → **Big (B)**

**Step 2: B/M sort**
- Use **NYSE 30th and 70th percentiles** of B/M as breakpoints
- Bottom 30% → **Low (L)** (growth stocks)
- Middle 40% → **Medium (M)**
- Top 30% → **High (H)** (value stocks)

**Why NYSE breakpoints?** Because NASDAQ has many tiny stocks. If we used all stocks for breakpoints, the "Small" group would be enormous and the "Big" group would be tiny. NYSE breakpoints ensure a more balanced split.

**Step 3: Intersect to form 6 portfolios**

|  | Low B/M | Medium B/M | High B/M |
|--|---------|------------|----------|
| **Small** | SL | SM | SH |
| **Big** | BL | BM | BH |

Each portfolio's monthly return is **value-weighted** (weighted by market cap).

---

## Implementation Details

### Book Equity (BE) — Davis, Fama, and French (2000)

```
SE = Stockholders' Equity (seq)
     → if missing: Common Equity + Preferred Stock (ceq + pstk)
     → if missing: Total Assets − Total Liabilities (at − lt)

PS = Preferred Stock: pstkrv → pstkl → pstk → 0

BE = SE + Deferred Taxes (txditc) − PS
```

### Market Equity (ME)

```
ME = |Price| × Shares Outstanding / 1000
   = abs(prc) × shrout / 1000  →  in millions of dollars
```

CRSP stores `prc` in dollars and `shrout` in thousands of shares.

### Data Filters

| Filter | Reason |
|--------|--------|
| `shrcd IN (10, 11)` | Common stock only (no ADRs, REITs, etc.) |
| `exchcd IN (1, 2, 3)` | NYSE, AMEX, NASDAQ |
| `siccd NOT 6000-6999` | Exclude financial firms (banks, insurance) |
| Delisting return adjustment | Avoid survivorship bias |
| `BE > 0` | Negative book equity is economically meaningless |
| B/M winsorized at 1%/99% | Remove extreme outliers |

### Risk-Free Rate

We use the **1-month T-Bill rate** from Kenneth French's website. If unavailable, we fall back to CRSP's `t30ret`.

---

## Quick Start

### Prerequisites

```bash
pip install wrds pandas numpy pandas-datareader
```

You need a **WRDS account** (typically provided by your university).

### Setup

1. Copy the example file and fill in your credentials:
```bash
cp env_example.txt .env
```

2. Edit `.env` with your WRDS account:
```
WRDS_USERNAME=your_username
WRDS_PASSWORD=your_password
```

> ⚠️ `.env` is in `.gitignore` and should never be shared or uploaded.

2. Run:
```bash
python main.py --start 2000-07-01 --end 2023-12-31
```

3. Output is saved to `output/ff3_factors.csv` with columns:
   - `date` — Month end date
   - `mkt_rf` — Market risk premium
   - `smb` — Small minus big
   - `hml` — High minus low
   - `rf` — Risk-free rate

---

## References

- Fama, E.F. and French, K.R. (1993). "Common risk factors in the returns on stocks and bonds." *Journal of Financial Economics*, 33(1), 3-56.
- Davis, J.L., Fama, E.F. and French, K.R. (2000). "Characteristics, Covariances, and Average Returns: 1929 to 1997." *Journal of Finance*, 55(1), 389-406.
- Kenneth French's Data Library: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html

---

---

# 한국어 설명

---

## Fama-French 3 Factor 모델이란?

1993년, Eugene Fama와 Kenneth French는 **주식 수익률을 3가지 요인으로 설명할 수 있다**는 획기적인 논문을 발표했습니다.

그 이전에는 CAPM(자본자산가격결정모형)이 지배적이었습니다:

```
기대수익률 = 무위험수익률 + β × (시장수익률 − 무위험수익률)
```

하지만 Fama와 French는 이것만으로는 부족하다는 것을 보여주었습니다. **소형주**와 **가치주**(장부가 대비 시장가가 높은 주식)가 CAPM이 예측하는 것보다 지속적으로 높은 수익률을 기록했기 때문입니다.

```
기대수익률 = RF + β₁×(Mkt−RF) + β₂×SMB + β₃×HML
```

이 모델은 현재 **학술 재무금융의 표준 벤치마크**로, 포트폴리오 성과 평가, 자산가격이론 검증, 초과수익률(알파) 측정에 사용됩니다.

---

## 3가지 팩터 상세 설명

### 1. 시장 리스크 프리미엄 (Mkt−RF)

**정의:** 전체 주식시장 수익률에서 무위험수익률(1개월 T-Bill)을 뺀 값

**직관:** 주식은 국채보다 위험하므로, 투자자들은 주식을 보유하는 대가로 추가 수익률(프리미엄)을 요구합니다.

**계산:**
```
Mkt−RF = 시가총액 가중 전체 주식 수익률 − 1개월 T-Bill 수익률
```
"시가총액 가중"이란 큰 회사일수록 평균에 더 큰 영향을 미친다는 뜻입니다.

---

### 2. SMB (Small Minus Big, 소형주 − 대형주)

**정의:** 소형주 수익률과 대형주 수익률의 차이

**직관:** 역사적으로 소형주가 대형주보다 높은 수익률을 기록했습니다. 왜일까요?
- 소형주는 더 위험합니다 (변동성이 크고, 사업이 덜 다각화됨)
- 소형주는 유동성이 낮습니다 (매매가 어려움)
- 소형주는 정보 비대칭이 큽니다

**계산:**
```
SMB = 소형 3개 포트폴리오 평균 − 대형 3개 포트폴리오 평균
    = (SL + SM + SH)/3 − (BL + BM + BH)/3
```

---

### 3. HML (High Minus Low, 가치주 − 성장주)

**정의:** 가치주(높은 B/M)와 성장주(낮은 B/M)의 수익률 차이

**직관:** "가치주"는 시장가격이 장부가치에 비해 낮은 회사입니다 — 시장이 비관적으로 평가하는 회사죠. 역사적으로 이런 주식이 "성장주"(인기 있고 비싼 회사)보다 높은 수익률을 기록했습니다.

**장부가 대 시가 비율 (Book-to-Market):**
```
B/M = 장부가치(Book Equity) / 시장가치(Market Equity)
```
- **높은 B/M** → 가치주 (저평가, 비인기)
- **낮은 B/M** → 성장주 (고평가, 인기)

**계산:**
```
HML = 높은 B/M 2개 포트폴리오 평균 − 낮은 B/M 2개 포트폴리오 평균
    = (SH + BH)/2 − (SL + BL)/2
```

---

## 포트폴리오 구성 방법

### 타임라인

```
t-1년 12월:  재무제표에서 장부가치(BE) 측정
t년 6월:     BE(t-1,12월) / ME(t,6월)로 포트폴리오 구성
t년 7월 ~ t+1년 6월:  매월 포트폴리오 수익률 계산
t+1년 6월:   포트폴리오 재구성 (연 1회)
```

### 왜 6개월 지연(lag)을 두나요?

2022년 12월 결산 재무제표는 보통 2023년 3~4월에야 공시됩니다. 2023년 6월에 사용하면 투자자가 **실제로 알 수 있었던 정보**만 사용하게 됩니다. 이를 통해 **미래 정보 편향(look-ahead bias)**을 방지합니다.

### 2×3 분류 절차

**1단계: 규모(Size) 분류**
- **NYSE 주식만**의 시가총액 중앙값을 기준점으로 사용
- 중앙값 이하 → **소형(S)**, 초과 → **대형(B)**

**2단계: B/M 분류**
- **NYSE 주식만**의 B/M 30%, 70% 분위수를 기준점으로 사용
- 하위 30% → **Low (L)** (성장주)
- 중간 40% → **Medium (M)**
- 상위 30% → **High (H)** (가치주)

**왜 NYSE 기준점을 사용하나요?** NASDAQ에는 아주 작은 주식이 많습니다. 전체 주식으로 기준점을 잡으면 "소형" 그룹이 지나치게 커지고 "대형" 그룹이 너무 작아집니다.

**3단계: 교차하여 6개 포트폴리오 구성**

|  | 낮은 B/M | 중간 B/M | 높은 B/M |
|--|----------|----------|----------|
| **소형** | SL | SM | SH |
| **대형** | BL | BM | BH |

각 포트폴리오의 월별 수익률은 **시가총액 가중**으로 계산합니다.

---

## 구현 세부사항

### 장부가치(Book Equity) 계산 — Davis, Fama, French (2000)

```
SE = 주주자본 (seq)
     → 없으면: 보통주자본 + 우선주 (ceq + pstk)
     → 없으면: 총자산 − 총부채 (at − lt)

PS = 우선주: pstkrv → pstkl → pstk → 0

BE = SE + 이연법인세 (txditc) − PS
```

### 데이터 필터

| 필터 | 이유 |
|------|------|
| `shrcd IN (10, 11)` | 보통주만 (ADR, REIT 등 제외) |
| `exchcd IN (1, 2, 3)` | NYSE, AMEX, NASDAQ |
| `siccd 6000-6999 제외` | 금융업 제외 (은행, 보험 등) |
| 델리스팅 수익률 보정 | 생존편향 방지 |
| `BE > 0` | 음수 장부가치는 경제적 의미 없음 |
| B/M 1%/99% winsorize | 극단값 제거 |

---

## 실행 방법

### 사전 준비

```bash
pip install wrds pandas numpy pandas-datareader
```

WRDS 계정이 필요합니다 (보통 대학에서 제공).

### 설정

1. 예시 파일을 복사하고 본인의 계정 정보를 입력하세요:
```bash
cp env_example.txt .env
```

2. `.env` 파일을 편집하여 WRDS 계정 정보를 입력:
```
WRDS_USERNAME=your_username
WRDS_PASSWORD=your_password
```

> ⚠️ `.env` 파일은 본인만 사용하는 파일입니다. 절대 다른 사람과 공유하거나 업로드하지 마세요.

2. 실행:
```bash
python main.py --start 2000-07-01 --end 2023-12-31
```

3. 결과는 `output/ff3_factors.csv`에 저장됩니다:
   - `date` — 월말 날짜
   - `mkt_rf` — 시장 리스크 프리미엄
   - `smb` — 소형주 − 대형주
   - `hml` — 가치주 − 성장주
   - `rf` — 무위험수익률

---

## 참고문헌

- Fama, E.F. and French, K.R. (1993). "Common risk factors in the returns on stocks and bonds." *Journal of Financial Economics*, 33(1), 3-56.
- Davis, J.L., Fama, E.F. and French, K.R. (2000). "Characteristics, Covariances, and Average Returns: 1929 to 1997." *Journal of Finance*, 55(1), 389-406.
- Kenneth French's Data Library: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
