# 배양기 예약 시스템 — 예약 로직 명세서 (플랫폼 이전용)

> **대상 독자:** 이 앱을 다른 플랫폼으로 재개발할 개발자
> **기준 코드:** `Server_code/` 폴더 (Streamlit 앱 + `sandbox_v2` FastAPI/React 샌드박스)
> **작성 방식:** 소스 코드를 직접 추적하여 작성함. 앱을 실행해 검증하지는 않았음.
> **표기:** 각 규칙 옆의 `파일:줄번호`는 근거 코드 위치. 경로는 `Server_code/` 기준.

이 문서는 "현재 코드가 실제로 어떻게 동작하는가"를 기술한다. 의도와 다르게 보이는 동작은 지우지 않고 그대로 적은 뒤 **⚠️ 주의**로 표시했다. 새 플랫폼에서 그대로 옮길지, 고칠지는 14장의 목록을 보고 결정하면 된다.

---

## 목차

1. 시스템 구성 개요
2. 데이터 모델 (저장 파일과 컬럼)
3. 설비(Inventory) 모델과 ID 규칙
4. 날짜·기간 규칙 (가장 중요)
5. 가용성 검사 (`check_availability`)
6. 배양기 예약 위저드 (Forward / Reverse)
7. Ambr 예약
8. 사용 불가 블록 (BLOCK / VBLOCK)
9. 관리자 기능
10. 비용 산출
11. 홈 대시보드 (가동률, 일정 알림, Gantt 표시 규칙)
12. 시뮬레이션 샌드박스 (드래그 앤 드롭 편집)
13. 인증과 권한
14. 이전 시 반드시 결정해야 할 불일치·버그 목록
15. 부록: 상수 표

---

## 1. 시스템 구성 개요

| 구성요소 | 파일 | 역할 |
|---|---|---|
| 홈 (공개) | `Home.py` | 층/Ambr별 Gantt, 가동률, 당일·익일 시작 일정 |
| 비용 | `pages/1_Cost.py` | 제품별·기간별 N-stage 비용 |
| 시뮬레이션 | `pages/2_Simulation.py` | React 샌드박스를 iframe으로 표시 |
| 예약 | `pages/3_Reservation.py` | 배양기 위저드, Ambr 위저드 |
| 관리자 | `pages/4_Admin.py` | 예약 편집/삭제, 블록, 백업/복원, 감사 로그, 일괄 Import |
| 공통 로직 | `utils.py` | 설비 생성, 가용성, 비용, 가동률, Gantt, 백업 |
| 인증 | `auth.py`, `users.yaml` | 로그인, 역할, 잠금, 유휴 타임아웃 |
| 샌드박스 API | `sandbox_v2/backend/main.py`, `utils.py`, `auth_utils.py` | 단일 사용자 잠금 기반 편집 → 적용 |
| 샌드박스 UI | `sandbox_v2/frontend/src/*.jsx` | 드래그 Gantt, 검색·추가, 변경 내역, 적용 |
| 백엔드 자동 실행 | `_sandbox_server.py` | Streamlit 기동 시 uvicorn(포트 8561) 실행 |

**저장소는 데이터베이스가 아니라 CSV 파일 하나**(`Bioreactor_reservation.csv`)다. 모든 화면이 이 파일 전체를 읽고, 저장할 때는 파일 전체를 덮어쓴다. 동시성 제어(파일 잠금, 트랜잭션)는 없다.

`sandbox_v2/backend/utils.py`는 Streamlit `utils.py`에서 Streamlit 의존성만 걷어낸 사본이다. 설비 표, 색상 표, EQ 매핑, 가용성 로직은 두 파일이 동일하다(확인함). 차이는 백엔드 인벤토리에 `eq_num` 필드가 추가된 것 하나다.

---

## 2. 데이터 모델

### 2.1 예약 파일 `Bioreactor_reservation.csv`

한 행 = 한 설비(배양기, Ambr250 vessel, 또는 Ambr15 station)의 한 기간 점유.

| 컬럼 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `booking_id` | 문자열 | ✔ | 고유 ID. 접두어로 생성 경로를 구분 (2.2 참고) |
| `reactor_id` | 문자열 | ✔ | 설비 ID (3장) |
| `user` | 문자열 | ✔ | SME 이름 (자유 입력). 블록은 `Admin (<로그인ID>)` |
| `start` | 날짜 | ✔ | 시작일 (`YYYY-MM-DD`, 시간 정보 없음) |
| `end` | 날짜 | ✔ | 종료일. **규칙은 4장 참고** |
| `project` | 문자열 | ✔ | 제품명 (자유 입력, 예: `SB27`). 블록은 `수리중` |
| `stage` | 문자열 | ✔ | `N-4`,`N-3`,`N-2`,`N-1`,`N`, 블록은 `Block`/`VesselBlock` |
| `method` | 문자열 | ✔ | 공정 (`Fed-batch`,`EFB`,`iEFB`,`N1`,`EN1`,`Perfusion`,`Unknown`,`N/A`) |
| `vessels_used` | 정수 | 선택 | Ambr15 station 예약에만 기록. 사용 vessel 수 (1–12) |

**읽기 규칙** (`utils.py:136`, 백엔드 `utils.py:140`):
- 인코딩을 `utf-8-sig → utf-8 → cp949 → euc-kr → latin1 → iso-8859-1` 순서로 시도한다.
- 모든 컬럼을 문자열로 읽은 뒤 `start`, `end`만 날짜로 변환한다. 변환에 실패한 행은 **조용히 제외**된다.
- `method` 컬럼이 없거나 비어 있으면 `Unknown`으로 채운다.
- `stage`가 `ambr run`(대소문자 무관)이면 `N`으로 바꾼다. 과거 데이터 호환용이다.

**쓰기 규칙** (`utils.py:176`): `utf-8-sig`로 파일 전체를 덮어쓴다.

### 2.2 `booking_id` 접두어 = 생성 경로

| 형식 | 생성 위치 | 의미 |
|---|---|---|
| `{unix초}_{stage순번}_{설비순번}` | 배양기 위저드 (`3_Reservation.py:293`) | 일반 예약 |
| `AMBR_{unix초}_{step}_{순번}` | Ambr 위저드 (`3_Reservation.py:499`) | Ambr 예약 |
| `BLOCK_{unix초}_{순번}` | 관리자 블록 (`4_Admin.py:401`) | 설비 단위 사용 불가 |
| `VBLOCK_{unix초}_{순번}` | 관리자 블록 | Ambr15 vessel 단위 사용 불가 |
| `GANTT_{unix초}_{순번}` | 관리자 일괄 Import (`4_Admin.py:625`) | Excel Gantt에서 가져온 예약 |
| `DRAG_{uuid 12자리}` | 샌드박스 (`main.py` `_new_booking_id`) | 샌드박스에서 추가하거나 이동한 예약 |

**`BLOCK_`과 `VBLOCK_` 접두어는 로직이 직접 참조한다.** VBLOCK은 가용성 검사에서 제외되고 비용의 vessel 수 차감에 쓰인다(5장, 10장). 따라서 새 플랫폼에서 접두어 대신 별도 필드(예: `kind = booking | block | vessel_block`)를 두는 것이 좋다.

### 2.3 부가 파일 (`DATA_DIR/simulations/` 아래)

| 경로 | 내용 |
|---|---|
| `pending/SIM_{사용자}_{YYYYmmdd_HHMMSS}.csv` | 샌드박스 변경분(diff). 예약 컬럼 + `_diff_action`(`added`/`removed`) |
| `applied/` | 적용이 끝난 diff 파일 (pending에서 이동) |
| `backups/BACKUP_{YYYYmmdd_HHMMSS}.csv` | 예약 파일 전체 스냅샷. **최신 10개만 유지** |
| `audit_log.csv` | `timestamp, action, filename, submitted_by, actioned_by` |

`audit_log`의 `action` 값은 `applied`(샌드박스 적용), `block_created`, `block_cleared`, `restored` 네 가지다.

### 2.4 데이터 경로 `DATA_DIR`

- Streamlit `utils.py:13`: 환경변수 `DATA_DIR`. 기본값 `""`, 즉 **Streamlit을 실행한 현재 폴더**다.
- 샌드박스 백엔드 `utils.py`: 환경변수 `DATA_DIR`. 기본값 `<backend>/../../Bioreactor_5`.
- ⚠️ **주의:** 환경변수를 설정하지 않으면 두 프로그램이 서로 다른 CSV를 볼 수 있다. 운영 서버에서는 폴더 배치로 두 경로가 같아지도록 맞춰져 있는 것으로 보인다. 새 플랫폼에서는 저장소를 하나로 통일하면 이 문제가 사라진다.

---

## 3. 설비(Inventory) 모델과 ID 규칙

설비 목록은 DB가 아니라 **코드 상수 `INVENTORY_CONFIGS`에서 매번 생성**한다 (`utils.py:51`, 생성 함수 `utils.py:179`).

각 설정 행은 `(scale, type, prefix, 시작번호, 끝번호, is_perfusion, room)`이다.

### 3.1 ID 생성 규칙

```
Ambr15:                 {room}-{prefix}-S{i}            예: Ambr15-EQ00000257-S1
5L 이면서 Perfusion:     {room}-{prefix}-P{i:02d}        예: 6층-5L-P01
그 외 Perfusion:         {room}-{prefix}-P{i}            예: 6층-2L-P1
그 외:                   {room}-{prefix}-{i:02d}         예: 6층-2L-05, Ambr250-EQ00005350-01
```

Ambr 계열은 `room` 자리에 시스템명(`Ambr250`/`Ambr15`), `prefix` 자리에 장비 EQ 번호가 들어간다. 그래서 ID 구조는 `시스템-EQ번호-vessel(또는 station)`이 된다.

Ambr15 vessel 단위 블록에서만 쓰는 하위 ID가 있다: `Ambr15-EQ00000257-S1-V03` (station ID + `-V01`~`-V12`). 이 ID는 인벤토리에는 없다.

### 3.2 생성되는 설비 (총 306개)

| 위치 | Scale | Type | 수량 | 번호 범위 / 예시 |
|---|---|---|---|---|
| 6층 | 5L | Fed-batch | 8 | 01–08 |
| 6층 | 5L | Perfusion | 3 | P01–P03 |
| 6층 | 2L | Double | 22 | 01–10, 17–22, 87–92 |
| 6층 | 2L | Single_Seed | 6 | 11–16 |
| 6층 | 2L | Single_New | 24 | 23–46 |
| 6층 | 2L | Single_300cc | 28 | 47–74 |
| 6층 | 2L | Single_150cc | 12 | 75–86 |
| 6층 | 2L | Perfusion | 24 | P1–P24 |
| 6층 | Wave | Wave | 3 | 03–05 |
| 5층 | Wave | Wave | 2 | 01–02 |
| 5층 | 5L | Fed-batch | 4 | 01–04 |
| 5층 | 10L | Fed-batch | 2 | 01–02 |
| 5층 | 50L | Fed-batch | 4 | 01–04 |
| 5층 | 200L | Fed-batch | 5 | 01–05 |
| 7층 | Wave | Wave | 2 | 06–07 |
| 7층 | 2L | Fed-batch | 12 | 01–12 |
| 7층 | 10L | Fed-batch | 2 | 01–02 |
| 7층 | 50L | Fed-batch | 2 | 05–06 |
| 7층 | 200L | Fed-batch | 1 | 06 |
| Ambr250 | Ambr250 | 24way | 24 | EQ00005350 × 01–24 |
| Ambr250 | Ambr250 | 12way | 96 | 8개 장비 × 01–12 |
| Ambr15 | Ambr15 | 48way | 20 | 5개 장비 × S1–S4 |

- **Ambr15의 예약 단위는 station**이다. 1 station = 12 vessel (`utils.py:183`).
- **Ambr250의 예약 단위는 vessel**이다. 한 행 = vessel 1개.
- 설비 속성: `id, name, scale, type, location("Room {room}"), status("Active")`. `status`는 항상 `Active`이고 로직에서 쓰이지 않는다.
- `type`이 로직에 쓰이는 곳은 단 한 곳이다. N-1 stage를 Perfusion으로 고르면 후보를 `type == 'Perfusion'`으로 거른다 (6장).
- 배양기 → 사내 EQ 번호 매핑은 `REACTOR_EQ_MAP`(`utils.py:90`)에 있고, 화면 라벨에만 쓰인다.

### 3.3 정렬 규칙 `custom_sort_key` (`utils.py:461`)

배양기 후보와 Gantt 행은 다음 4단계 키로 정렬한다.

1. 층: 6층 → 5층 → 7층
2. Scale: 5L → 2L → 10L → 50L → 200L → Wave
3. Perfusion 여부: 일반 먼저, `P` 번호 나중
4. 번호 (숫자 기준)

Ambr 설비는 `INVENTORY_CONFIGS`에 적힌 장비 순서대로 정렬한다 (`Home.py:258`). 프론트엔드 `ganttUtils.js` `reactorSortKey`도 같은 규칙을 쓰며, `S` 접두어도 숫자로 취급한다.

---

## 4. 날짜·기간 규칙 (가장 중요)

이 장의 규칙이 예약 충돌 판정, 화면 표시, 비용 계산 전체에 영향을 준다. 새 플랫폼에서 날짜를 다르게 해석하면 기존 데이터의 충돌 판정 결과가 달라진다.

### 4.1 저장 규칙: `end = start + 배양일수`

위저드는 `end = start + timedelta(days=배양일수)`로 저장한다 (`3_Reservation.py:246, 210, 397`).
예: 4일 배양을 6/1에 시작하면 `start=6/1`, `end=6/5`로 저장된다.

### 4.2 충돌 규칙: 반열린 구간(half-open) — 같은 날 교대 허용

가용성 검사는 **엄격한 부등호**를 쓴다 (`utils.py:451`).

```
겹침  ⇔  기존.start < 신규.end  AND  기존.end > 신규.start
```

즉 예약 구간을 `[start, end)`로 본다. **기존 예약의 `end`와 신규 예약의 `start`가 같은 날이면 겹침이 아니다.** 한 배양기에서 같은 날 앞 배양을 끝내고 다음 배양을 시작할 수 있다는 뜻이다.

### 4.3 표시 규칙: `end`일도 칠해짐 (= 배양일수 + 1칸)

- Streamlit Gantt는 막대를 `start 00:00` ~ `end 23:59:59`로 그린다 (`utils.py:648`). React Gantt도 너비를 `(end − start + 1)일`로 계산한다 (`Gantt.jsx:307`). 그래서 4일 배양이 화면에서는 5칸을 차지한다.
- 위저드 확인 화면은 기간을 `(end − start).days + 1`일로 표시한다 (`3_Reservation.py:279`).
- 같은 배양기에서 앞 예약의 `end`와 뒤 예약의 `start`가 같은 날이면, 그 날을 **정오(12:00)에서 반씩 나눠** 그린다 (`utils.py:652–657`).
- 막대 라벨의 일수는 `(end − start).days`다 (`utils.py:677`). 같은 화면에서 숫자가 1 다르게 보일 수 있다.

### 4.4 다른 곳에서 쓰는 "닫힌 구간" 판정

다음 기능은 `start ≤ 기간끝 AND end ≥ 기간시작`인 **양끝 포함(inclusive)** 판정을 쓴다. 4.2와 해석이 다르다.

| 기능 | 위치 |
|---|---|
| 블록 생성 시 기존 예약 삭제 범위 | `4_Admin.py:393–397` |
| 비용 기간 필터 | `utils.py:419`, `1_Cost.py:127` |
| VBLOCK의 vessel 수 차감 | `utils.py:318` |
| 가동률(일수 계산, 양끝 포함) | `utils.py:493` |
| 홈 Gantt 표시 범위 | `Home.py:174` |

⚠️ **주의:** 블록 삭제가 inclusive이기 때문에, 블록 시작일에 끝나는 예약도 지워질 수 있다. 충돌 목록(4.2 기준)에는 나타나지 않았던 예약이다. 자세한 내용은 8.3과 14장에 있다.

**권장:** 새 플랫폼에서는 하나의 구간 정의(`[start, end)` 권장)를 정하고 모든 기능에 동일하게 적용한다. 화면에서 `end`일을 칠할지는 별도의 표시 옵션으로 둔다.

---

## 5. 가용성 검사 `check_availability`

위치: `utils.py:437` (백엔드 `utils.py:198`, 로직 동일)

```
입력: reactor_id, start, end, bookings, allow_same_day=True
1. bookings가 비었으면 → 가능
2. 해당 reactor_id의 행만 남김 (문자열 완전 일치)
3. booking_id가 'VBLOCK_'으로 시작하는 행 제외
   → vessel 블록은 station 예약을 막지 않음
4. 겹침(4.2 기준) 행이 하나라도 있으면 → 불가
5. allow_same_day == False 이면:
      end >= 신규.start 인 행이 하나라도 있으면 → 불가
6. → 가능
```

- **BLOCK_ 행은 일반 예약과 똑같이 취급**된다. 그래서 블록 기간에는 예약이 막힌다.
- ⚠️ **주의 (5단계):** 4단계를 통과한 행은 신규 기간보다 완전히 앞이거나 완전히 뒤에 있다. 그런데 5단계 조건 `end >= 신규.start`는 **신규 기간보다 뒤에 있는 미래 예약에도 참**이 된다. 그래서 `allow_same_day=False`이면 그 배양기에 이후 예약이 하나라도 있을 때 후보에서 빠진다. 의도는 "같은 날 교대 제외"였던 것으로 보인다. 주석으로 남은 `buffer_end` 변수가 그 근거이며, 이 변수는 쓰이지 않는다.
- 배양기 위저드의 체크박스(라벨 `털들 배양기 포함`, 기본값 **해제**)가 이 값을 정한다. 따라서 **기본 상태에서는 5단계가 적용된다** (`3_Reservation.py:193`).
- 그 밖의 모든 호출(Ambr 위저드, 블록, Import, 샌드박스)은 기본값 `True`를 쓴다.

---

## 6. 배양기 예약 위저드

위치: `pages/3_Reservation.py:56–314`. 권한: `editor` 이상.

### 6.1 입력

- 제품명(`project`), SME(`user`): 둘 다 필수, 자유 텍스트
- 기준일(`anchor_date`): Forward면 **N-4 시작일**, Reverse면 **N 시작일**
- Stage 행 목록. 기본값은 아래와 같다 (`3_Reservation.py:95`).

| Stage | Scale | 배양일수 | 배양기 수 | Method |
|---|---|---|---|---|
| N-4 | 2L | 4 | 2 | Fed-batch |
| N-3 | 2L | 4 | 2 | Fed-batch |
| N-2 | 2L | 4 | 3 | Fed-batch |
| N-1 | 5L | 5 | 2 | Fed-batch |
| N | 2L | 11 | 12 | Fed-batch |

- Stage 선택지: `N-4, N-3, N-2, N-1, N`. 행 추가·삭제가 가능하다. 추가된 행의 기본값은 2L, 4일, 3대다.
- Scale 선택지: `2L, 5L, 10L, Wave, 50L, 200L`.
- Method 규칙 (`3_Reservation.py:128–166`):
  - **N**: scale별 선택지 (15.1 표)
  - **N-1**: `Fed-batch` 또는 `Perfusion`
  - **그 외 Stage**: `Fed-batch` 고정
- 배양일수와 배양기 수는 1 이상의 정수다.
- Stage 행은 **입력한 순서대로 연결**된다. Stage 이름으로 다시 정렬하지 않는다.

### 6.2 일정 계산

**Forward** (`3_Reservation.py:243`)
```
curr = anchor_date
각 stage에 대해 (입력 순서대로):
    start = curr
    end   = curr + days
    curr  = end            ← 다음 stage는 이전 stage의 end일에 시작
```

**Reverse** (`3_Reservation.py:203`)
```
stage 목록을 뒤집어서 (마지막 행 = N부터):
    첫 번째(N):  start = anchor_date,  end = anchor_date + days
    이후:        end = 바로 뒤 stage의 start,  start = end − days
모든 stage 계산이 끝난 뒤:
    가장 이른 start < 오늘 이면 → 오류
       ("N 시작일을 최소 {차이}일 늦추세요"), 중단
결과를 다시 뒤집어 시간순(N-4 → N)으로 저장
```
- Forward에는 "오늘 이전" 검사가 **없다**. 과거 날짜로도 예약할 수 있다.
- 모드를 바꾸면 이전 검색 결과는 지워진다.

### 6.3 후보 설비 선정

```
후보 = 인벤토리에서 scale == stage.scale 인 설비 (모든 층)
stage == 'N-1' 이고 method == 'Perfusion' 이면 → type == 'Perfusion' 만
각 후보에 check_availability(id, start, end, 전체예약, allow_same_day=체크박스)
통과한 것을 custom_sort_key 순으로 정렬
```
- 층 필터는 없다. 2L stage 후보에는 6층과 7층 2L이 모두 포함된다.
- Perfusion이 아닌 stage에도 Perfusion 전용 배양기(예: `6층-2L-P1`)가 후보에 들어간다. 정렬 규칙상 목록 뒤쪽에 놓인다.
- 각 stage의 후보는 **서로 독립적으로** 계산된다. 같은 캠페인 안의 다른 stage와는 대개 기간이 붙어 있을 뿐 겹치지 않으므로 보통 문제가 없다. 다만 같은 scale이고 기간이 겹치는 stage 행이 두 개 있으면 같은 배양기를 둘 다에 고를 수 있다. 저장 시점에 충돌을 다시 검사하지 않는다.

### 6.4 확정·저장 (`3_Reservation.py:287–314`)

- stage마다 정확히 `배양기 수`만큼 선택해야 한다. 후보가 부족하면 "Need X, Found Y"를 띄우고 진행할 수 없다.
- 제품명과 SME가 비어 있으면 오류다.
- 선택한 설비 하나당 한 행을 만든다: `booking_id = {unix초}_{stage순번}_{설비순번}`, `stage`, `method`, `start`, `end`는 계산값.
- 기존 예약에 덧붙여 **CSV 전체를 저장**한다.
- ⚠️ **주의:** 저장 직전에 가용성을 다시 확인하지 않는다. 검색과 저장 사이에 다른 사람이 같은 배양기를 예약하면 중복 예약이 생긴다.

---

## 7. Ambr 예약

위치: `pages/3_Reservation.py:317–516`. 권한: `editor` 이상.

### 7.1 입력

- 제품명, SME (필수), 시작일
- 시스템 행 목록. 기본값은 Ambr250, 7일, 1개, EFB다. 행을 추가하면 Ambr250, 15일, 12개, EFB가 들어간다.
- System: `Ambr250` 또는 `Ambr15`
- Method: Ambr250은 `EFB, iEFB, EN1`, Ambr15는 `Fed-batch`
- 수량: Ambr250이면 **vessel 수**, Ambr15이면 **station 수**

### 7.2 일정과 후보 (`3_Reservation.py:394`)

```
curr = 시작일
각 행:
   start = curr,  end = curr + days,  curr = end   (Forward 연결, 배양기와 동일)
   후보 = id가 scale명으로 시작하는 설비 중 check_availability 통과
          (allow_same_day = True)
   stage = 'N' 고정
```

### 7.3 선택 규칙 (`3_Reservation.py:423–487`)

- 후보를 **EQ 번호(장비)로 묶는다**. 한 step에서는 **장비 1대만** 고를 수 있다.
- 고른 장비 안에서 vessel(또는 station)을 정확히 수량만큼 고른다. 기본 선택은 앞에서부터 수량만큼이다.
- **Ambr15 전용:** station마다 "12개 미만 사용" 체크박스가 있다. 체크하면 사용 vessel 수(1–12)를 입력하고, 체크하지 않으면 12다. 이 값이 `vessels_used`에 저장된다.
- Ambr250은 `vessels_used = 1`로 저장된다.

### 7.4 저장

`booking_id = AMBR_{unix초}_{step}_{순번}`, `stage='N'`, `vessels_used`를 포함해 CSV 전체를 저장한다. 6.4와 같이 저장 직전 재검사는 없다.

---

## 8. 사용 불가 블록 (고장·Calibration)

위치: `pages/4_Admin.py:127–490`. 권한: `admin`.

### 8.1 두 종류의 블록

| 구분 | `booking_id` | 대상 ID | 예약을 막는가 | 기존 예약 삭제 | 용도 |
|---|---|---|---|---|---|
| 설비 블록 | `BLOCK_…` | 배양기, Ambr250 vessel, Ambr15 station | **막음** | 겹치는 예약 **삭제** | 고장/수리/Calibration |
| Vessel 블록 | `VBLOCK_…` | Ambr15 vessel (`…-S1-V03`) | 막지 않음 | 삭제 안 함 | station 안 일부 vessel 고장. 비용 차감용 |

공통 필드: `project='수리중'`, `stage='Block'` 또는 `'VesselBlock'`, `method='N/A'`, `user='Admin (<로그인ID>)'`.

### 8.2 생성 절차

1. 시작일과 종료일을 입력한다. 종료일 < 시작일이면 오류다.
2. 사유를 고른다: `고장/수리중`, `Calibration 중`, `기타`(직접 입력). 사유는 필수다.
3. 대상 범주를 고른다.
   - Bioreactor: 층 → Scale → 번호(복수 선택)
   - Ambr250: EQ → vessel 번호(복수 선택)
   - Ambr15: EQ → station. "vessel 단위 블록"을 켜면 V01–V12 중에서 고른다. **12개를 모두 고르면 자동으로 station 블록 1행으로 바뀐다.**
4. "Block List에 추가"로 대기열에 쌓는다. 중복은 건너뛴다. **설비 블록과 vessel 블록은 한 대기열에 섞을 수 없다.**
5. 설비 블록이면 대기열의 각 설비에 대해 `check_availability`로 충돌 설비 목록을 미리 보여준다.
6. "Create Block(s)"를 누르면 다음이 진행된다.
   - 충돌이 있으면 먼저 **자동 백업**을 만든다. 실패하면 중단한다.
   - 충돌 설비들에서 블록 기간과 **겹치는 예약을 삭제**한다 (8.3).
   - 블록 행을 추가하고 CSV를 저장한다.
   - 감사 로그에 `block_created`를 남긴다 (`submitted_by` 칸에 사유를 저장).

### 8.3 ⚠️ 삭제 범위 불일치

충돌 판정(5단계 함수)은 반열린 구간을 쓰고, 실제 삭제(`4_Admin.py:393`)는 양끝 포함 구간을 쓴다. 그래서 충돌 설비로 분류된 배양기에서는 **블록 시작일에 끝나거나 블록 종료일에 시작하는 예약까지 삭제**된다. 반면 그런 예약만 있는 배양기는 충돌로 분류되지 않으므로 아무것도 지워지지 않는다.

또 `utils.create_backup()`은 값을 반환하지 않는다. 그래서 완료 메시지와 감사 로그의 백업 파일명이 `None`/`N/A`로 남는다.

### 8.4 해제

활성 블록 목록에서 골라 행을 삭제하고 감사 로그에 `block_cleared`를 남긴다. 블록 생성 때 삭제된 예약은 **자동으로 복구되지 않는다**. 복구하려면 백업 복원을 써야 한다.

---

## 9. 관리자 기능

위치: `pages/4_Admin.py`. 권한: `admin`.

### 9.1 예약 표 편집 (`4_Admin.py:25–122`)

- 필터: 제품, Scale(인벤토리에서 조회), Method, 시작일(같은 날).
- 셀 편집 후 "Save Changes"를 누르면, 표에 보이는 모든 행을 `booking_id` 기준으로 원본에 덮어쓰고 CSV 전체를 저장한다.
- ⚠️ **주의:** 날짜나 설비를 바꿔도 **충돌 검사를 하지 않는다**.
- Method 편집 선택지는 `Unknown, Fed-batch, EFB, iEFB, N1, EN1`이다. N-1 위저드가 저장하는 `Perfusion`과 블록의 `N/A`가 선택지에 없어서, 이런 행은 편집 과정에서 값이 바뀌거나 검증에 걸릴 수 있다.
- 삭제: 체크한 행을 지우고 저장한다. 백업이나 감사 로그는 남지 않는다.
- `Unknown` method 건수를 경고로 보여준다. 이 행들은 비용 계산에서 단가 0이 된다.

### 9.2 백업·복원 (`4_Admin.py:494–587`)

- **수동:** 현재 예약을 CSV로 다운로드하거나, CSV를 업로드해 **전체를 교체**한다. 교체 시 날짜를 파싱하지 못한 행은 버리고, method가 비면 `Unknown`으로 채운다. 이때 자동 백업은 만들지 않는다.
- **자동 백업:** 최신 10개 목록에서 골라 복원하면 전체가 교체된다. 감사 로그에 `restored`가 남는데, 실행자는 실제 로그인 ID가 아니라 고정 문자열 `'Admin'`이다.
- **감사 로그:** 조회할 수 있고, 관리자가 **항목을 삭제할 수도 있다**. 변경 불가능한 기록이 아니다.

### 9.3 Excel Gantt CSV 일괄 Import (`4_Admin.py:589–748`)

- 필수 컬럼: `reactor_id, project, user, stage, method, start, end`. `booking_id`는 `GANTT_…`로 새로 만든다.
- 검증 단계에서는 인벤토리에 없는 `reactor_id`와 기존 예약과의 충돌 건수를 **경고만** 한다.
- 모드:
  - **Replace All:** 기존 예약을 모두 지우고 CSV로 교체한다. 충돌 검사도 백업도 없다.
  - **Add + Skip Conflicting:** 기존 예약과 충돌하는 행을 건너뛴다. 단 **Import 파일 안의 행끼리는 검사하지 않는다**.
  - **Add + Force Overwrite:** 각 Import 행과 겹치는(반열린 구간) 기존 예약을 지운 뒤 추가한다.
- 인벤토리에 없는 ID도 그대로 저장된다.

---

## 10. 비용 산출

위치: `utils.py:197–434`, `pages/1_Cost.py`. ⚠️ 이 페이지에는 **로그인 검사가 없다** (`1_Cost.py`에 `require_role` 호출 없음).

### 10.1 단가표

`1_Cost.py:13`의 **하드코딩 값**을 쓴다. 단위는 KRW, **vessel(또는 배양기) 1개당** 금액이다. 전체 값은 15.2 표에 있다.
`utils.load_cost_matrix()`는 `배치_단가.csv`를 읽는 함수지만 **현재 어느 화면에서도 호출되지 않는다**.

### 10.2 제품별 비용 `calculate_project_cost` (`utils.py:323`)

```
1. stage == 'N' 인 행만
2. project == 대상 제품 (문자열 완전 일치)
3. reactor_id에서 scale 추출:
      두 번째 토큰이 2L/5L/10L/50L/200L/Wave → 그 값
      첫 번째 토큰에 'Ambr' 포함 → 첫 번째 토큰 (Ambr250 / Ambr15)
4. scale ∈ {Ambr15, Ambr250, 2L, 200L} 만 남김
      → 5L, 10L, 50L, Wave의 N-stage는 비용 0 (집계에서 빠짐)
5. 행마다 vessel 수 = get_vessel_count(...)   (10.3)
6. (scale, method)로 묶어서:
      소계 = vessel 수 합 × 단가(scale, method)
      단가표에 없는 조합(예: Unknown) → 단가 0
7. 합계 = 소계의 합
```

결과 표의 표시 컬럼은 scale마다 다르다.

| Scale | Bioreactors | Stations | Vessels |
|---|---|---|---|
| 2L / 200L | 행 수 | – | – |
| Ambr250 | – | – | vessel 수 합 |
| Ambr15 | – | 행 수(station) | vessel 수 합 |

### 10.3 vessel 수 `get_vessel_count` (`utils.py:280`)

```
Ambr15 station이 아니면 → 1
vessels_used 값이 있으면 → int(float(vessels_used))
없으면 → 12 − (이 station 하위 vessel의 VBLOCK 중
               예약 기간과 겹치는(양끝 포함) 행 수),  최소 0
```

Ambr15 station 판별 조건은 `토큰 ≥ 3개, 첫 토큰 == 'Ambr15', 마지막 토큰이 'S'로 시작`이다.

⚠️ **주의:** Ambr 위저드는 Ambr15 예약에 **항상** `vessels_used`(기본 12)를 기록한다. 그래서 VBLOCK 차감은 `vessels_used`가 없는 과거 데이터에만 적용된다. 화면 문구("blocked vessels excluded from cost")와 실제 동작이 다르다.

### 10.4 기간별 비용 `calculate_monthly_costs` (`utils.py:403`, `1_Cost.py:102`)

- 기본 기간은 이번 달 1일부터 말일까지다.
- 기간과 **조금이라도 겹치는**(양끝 포함) 예약을 고른 뒤, 제품마다 10.2를 적용한다.
- ⚠️ **일할 계산을 하지 않는다.** 예약 기간 중 하루만 겹쳐도 그 예약의 비용 **전액**이 해당 기간에 잡힌다. 그래서 월별 합계를 더하면 같은 예약이 여러 달에 중복 집계될 수 있다.
- 합계가 0인 제품은 목록에서 빠진다.
- 표의 "N-Stage Reactors" 값은 vessel 수 합(`qty`)이다.
- 내보내기 CSV 컬럼: `Project, Scale, Method, Bioreactors, Stations, Vessels, Unit Cost (KRW per vessel), Subtotal (KRW)`.

---

## 11. 홈 대시보드

위치: `Home.py` (로그인 불필요).

### 11.1 데일리 시작 일정 (`Home.py:31–75`)

`start` 날짜가 오늘인 행, 내일인 행, 사용자가 지정한 날짜(기본 모레)인 행의 **개수와 목록**을 보여준다. 블록 행도 포함된다.

### 11.2 가동률 `calculate_generic_occupancy` (`utils.py:481`)

```
대상 = 화면 범위의 설비 ID 목록
         (배양기는 선택한 층의 전체 설비, Ambr는 시스템 전체)
월 = 이번 달, 다음 달
용량 = 설비 수 × 해당 월 일수
점유 = Σ(각 예약과 그 월이 겹치는 일수, 양끝 포함)
가동률 = 점유 / 용량 × 100
```
- BLOCK 행도 점유로 계산된다.
- VBLOCK은 ID가 인벤토리에 없으므로 계산에서 빠진다.
- 한 설비에 겹치는 예약이 있으면 두 번 세어지므로 100%를 넘을 수 있다.
- 같은 날 교대(앞 예약 end = 뒤 예약 start)인 날도 이틀분으로 세어진다.

### 11.3 Gantt 표시 규칙 (`utils.py:538`, React `Gantt.jsx`)

- 표시 범위: Streamlit은 오늘 −7일 ~ +63일, React는 오늘 −7일 ~ +100일.
- 주말과 한국 공휴일은 붉은 배경으로 칠한다. 공휴일은 `KR_HOLIDAYS`(`utils.py:501`)에 **2025–2027년만 하드코딩**되어 있다.
- 매월 1일에는 굵은 세로선을, 오늘 위치에는 빨간 세로선을 긋는다. 사용자가 지정한 날짜는 파란 선 두 개로 강조한다.
- 막대 색상: 제품명에서 정규식 `SB[ ._-]*(\d+)`로 `SB{번호}`를 뽑아 `PROJECT_BG_MAP` / `PROJECT_FONT_MAP`에서 색을 찾는다. 없으면 배경 회색(`#808080`), 글자 검정이다. `수리중`(블록)은 회색 배경에 빨간 글자다.
- 막대 라벨은 `{project} ({일수}d)`, 툴팁에는 제품, SME, 기간이 나온다.
- 홈 화면에서는 제품 필터를 최대 2개까지 걸 수 있다.
- Ambr15 탭 하단에는 표시 기간과 겹치는 VBLOCK 목록(station, vessel, 기간, 등록자)을 보여준다.
- 설비 라벨 색상(scale별): 2L `#BDD7EE`, 5L `#90EE90`, 10L `#32CD32`, 50L `#FFA500`, 200L `#CC0000`, Wave `#D3D3D3`.

---

## 12. 시뮬레이션 샌드박스 (드래그 앤 드롭 편집)

위치: `sandbox_v2/backend/main.py`, `sandbox_v2/frontend/src/App.jsx`, `Gantt.jsx`.
Streamlit 페이지(`2_Simulation.py`)는 `viewer` 이상이면 열 수 있다. 이 페이지는 `http://{host}:8561?user={로그인ID}`를 iframe으로 띄운다.

### 12.1 핵심 개념

- **단일 사용자 잠금:** 한 번에 한 사람만 편집할 수 있다. 잠금은 서버 메모리에만 있다.
- **사본 편집:** 잠금을 얻는 순간 실제 예약을 복사해 `sandbox_df`(편집용)와 `snapshot_df`(기준 시점)를 만든다. 편집은 모두 메모리 안에서만 일어난다.
- **적용(Apply)할 때만 디스크에 쓴다.** 적용하려면 editor 또는 admin 계정의 비밀번호를 다시 입력해야 한다.
- 서버가 재시작되면 잠금과 편집 내용이 모두 사라진다.

### 12.2 잠금 규칙

| 항목 | 값 |
|---|---|
| 유휴 만료 | 마지막 변경 후 **30분** (`LOCK_TIMEOUT_MINUTES`) |
| 만료 확인 시점 | 모든 API 호출의 시작 시점 (`_check_and_release_expired_lock`) |
| 활동 시간 갱신 | move / delete / undo / add 성공 시. 조회만 해서는 갱신되지 않는다 |
| 만료 경고 | 프론트엔드가 1분마다 조회하고, 남은 시간이 5분 이하이면 경고 |
| 탭을 닫을 때 | `beforeunload` 이벤트에서 `sendBeacon`으로 `/api/sandbox/unlock` 호출 |
| 새로고침 | `sessionStorage`의 사용자명과 잠금 소유자가 같으면 편집 상태를 이어서 복원 |

사용자 식별은 요청 본문의 `user` 문자열뿐이다. 입력창은 URL의 `?user=` 값으로 채워지지만 사용자가 고칠 수 있다. 자세한 내용은 13장에 있다.

### 12.3 편집 동작

| 동작 | 서버 규칙 | 클라이언트 규칙 |
|---|---|---|
| **이동** `move` | 원래 행을 지우고, 같은 내용에 **새 `DRAG_` ID**를 붙여 새 설비·날짜로 추가한다. **서버는 충돌을 검사하지 않는다.** | 하루 단위로 맞춘다(1일 = 22px). 행 단위로 설비를 바꾼다. 표시 범위 밖으로는 못 나간다. 여러 개를 선택하면 같은 거리만큼 함께 이동한다. 기존 막대가 **새 기간을 완전히 감싸는 경우에만** 드롭을 거부한다(`Gantt.jsx:233`). 부분 겹침은 허용된다. |
| **기간 조정** (막대 양끝) | `move`와 같다 | start < end를 유지한다 (최소 1일) |
| **삭제** `delete` | 행 제거 | – |
| **되돌리기** `undo` | 변경 직전 상태를 최대 **50단계**까지 보관하고 하나씩 되돌린다 | – |
| **검색** `find-available` | `end = start + days`. 잠금 중이면 `sandbox_df`, 아니면 실제 데이터 기준으로, scale이 같은 설비에 `check_availability`를 적용한다 | 수량만큼 앞에서부터 자동 선택한다. Ambr scale이면 stage를 N으로 고정한다 |
| **추가** `add` | 선택한 설비마다 `sandbox_df` 기준으로 충돌을 검사한다. 하나라도 충돌하면 **전체를 거부**(409)한다. 통과하면 `DRAG_` ID로 추가한다 | 제품명이 필수다 |

- 이동 결과가 "삭제 1건 + 추가 1건"으로 기록되기 때문에, **적용 후 원래 `booking_id`가 사라지고 `DRAG_` ID로 바뀐다**. 원래 ID에 연결된 외부 데이터가 있다면 그 연결이 끊긴다.
- 드래그로 다른 scale의 행(예: 2L 막대를 5L 행)으로 옮기는 것을 막지 않는다.
- VBLOCK 행은 샌드박스 Gantt에 그리지 않는다.

### 12.4 변경 내역 `diff` (`main.py:443`)

```
added   = sandbox에는 있고 snapshot에는 없는 booking_id
removed = snapshot에는 있고 sandbox에는 없는 booking_id
```
ID 집합만 비교한다. 같은 ID의 내용 변경은 감지하지 않지만, 샌드박스에는 ID를 유지한 채 내용을 바꾸는 동작이 없으므로 현재는 문제가 없다.

### 12.5 적용 `apply` (`main.py:473`)

```
1. IP별 실패 횟수 제한: 5분 안에 5회 실패하면 429
2. 잠금 소유자 == req.user 인지 확인
3. Authorization: Basic 헤더로 받은 계정의 비밀번호 검증 (PBKDF2)
   → 실패하면 실패 횟수 +1, 401
4. 계정 역할이 admin 또는 editor 인지 확인 → 아니면 403
5. 실제 데이터를 디스크에서 새로 읽음 (fresh_live)
6. user_added   = sandbox − snapshot
   user_removed = snapshot − sandbox
7. 충돌 검사 (user_added의 각 행):
      a) fresh_live에서 user_removed를 뺀 데이터와 겹치는지
         → 잠금 이후 다른 경로로 추가된 예약까지 반영됨
      b) 같은 변경 묶음 안의 다른 추가 행과 겹치는지
   하나라도 충돌하면 → 409와 충돌 목록, 아무것도 쓰지 않음
8. 백업 생성
9. diff 파일 저장 (pending/SIM_{계정}_{시각}.csv)
10. apply_simulation_diff: 다시 백업 → 실제 데이터 로드
    → removed ID 삭제 → added 행 추가 → CSV 저장 → diff 파일을 applied/로 이동
11. 감사 로그 'applied' (submitted_by = 인증 계정, actioned_by = 잠금 사용자)
12. 잠금 해제
```
- 7단계 이후 10단계 저장까지 다른 프로그램이 CSV를 쓰면, 그 변경을 덮어쓸 수 있다. 파일 잠금이 없기 때문이다.
- 백업이 연달아 두 번 만들어진다. 같은 초 안이면 같은 파일명으로 덮어쓴다.

### 12.6 API 목록

| Method | 경로 | 인증 | 설명 |
|---|---|---|---|
| GET | `/api/version` | – | API 버전(11). 오래된 백엔드를 감지하는 데 씀 |
| GET | `/api/inventory/eq-map` | – | 배양기 → EQ 번호 |
| GET | `/api/schedule` | – | 실제 예약, 설비 목록, 색상표, 잠금 상태 |
| POST | `/api/sandbox/lock` | user 문자열 | 잠금 획득. 다른 사람이 쓰는 중이면 423 |
| DELETE | `/api/sandbox/lock?user=` | user 문자열 | 잠금 해제 (적용 안 함) |
| POST | `/api/sandbox/unlock` | user 문자열 | 탭 닫힘 시 beacon용 해제 |
| GET | `/api/sandbox/bookings` | – | 샌드박스 상태 |
| POST | `/api/sandbox/move` | user 문자열 | 이동 / 기간 조정 |
| POST | `/api/sandbox/delete` | user 문자열 | 삭제 |
| POST | `/api/sandbox/undo` | user 문자열 | 되돌리기 |
| POST | `/api/sandbox/find-available` | – | 빈 설비 검색 |
| POST | `/api/sandbox/add` | user 문자열 | 예약 추가 |
| GET | `/api/sandbox/diff` | – | 변경 내역 |
| POST | `/api/sandbox/apply` | Basic (editor/admin) | 디스크에 적용 |
| POST | `/admin/shutdown` | **없음** | 프로세스 종료 (재기동용) |

HTTP 상태 코드: 423 = 잠금 없음 또는 타인 사용 중, 403 = 잠금 소유자 불일치 또는 역할 부족, 404 = 예약 없음, 409 = 충돌 또는 되돌릴 내역 없음, 429 = 실패 횟수 초과.

---

## 13. 인증과 권한

위치: `auth.py`, `users.yaml`, 백엔드 `auth_utils.py`.

- 계정 저장소: `users.yaml` → `credentials.usernames.{id}.{password, roles[], email, first_name, last_name}`
- 비밀번호 형식: `pbkdf2_sha256${반복횟수}${salt hex}${hash hex}`, 반복 200,000회, salt 16바이트. 비교는 상수 시간으로 한다.
- 역할 계층: `admin(2) > editor(1) > viewer(0)`. `roles`에 admin이 있으면 admin, editor가 있으면 editor, 둘 다 없으면 viewer다. 로그인하지 않은 사용자도 viewer로 취급한다.
- 로그인 5회 실패 시 5분 잠금. 단 **브라우저 세션 단위**라서 새 세션을 열면 초기화된다.
- 유휴 1시간이면 로그아웃된다. 쿠키를 쓰지 않으므로 새로고침하면 다시 로그인해야 한다.
- 계정 추가는 `add_user.py`가 담당한다.

| 페이지 / 동작 | 필요 권한 |
|---|---|
| 홈 | 없음 |
| 비용 | **없음** (검사 코드 없음) |
| 시뮬레이션 화면 | viewer (= 사실상 누구나) |
| 샌드박스 편집 API | 없음 (`user` 문자열만 일치하면 됨) |
| 샌드박스 적용 | editor/admin 비밀번호 재입력 |
| 예약 위저드 | editor |
| 관리자 | admin |

---

## 14. 이전 시 반드시 결정해야 할 불일치·버그 목록

아래는 현재 동작이다. 새 플랫폼에서 **유지할지 고칠지** 업무 담당자와 먼저 합의해야 한다. 근거가 되는 장도 함께 적었다.

| # | 현재 동작 | 영향 | 권장 | 근거 |
|---|---|---|---|---|
| 1 | `allow_same_day=False`(위저드 기본값)이면, 이후에 예약이 하나라도 있는 배양기가 후보에서 빠짐 | 빈 배양기가 부족하게 표시됨 | "같은 날 교대만 제외"로 수정하거나, 옵션 자체의 의미를 업무 담당자에게 확인 | 5장 |
| 2 | 충돌은 반열린 구간, 블록 삭제·비용·가동률은 양끝 포함 구간 | 블록 생성 시 인접 예약이 삭제될 수 있음. 일수 계산이 기능마다 다름 | 구간 정의를 하나로 통일 | 4장, 8.3 |
| 3 | 저장 직전에 가용성을 재검사하지 않음 (위저드, Ambr, 관리자 편집, Import) | 동시 사용 시 중복 예약 | 저장 트랜잭션 안에서 재검사. DB 고유성/배타 제약 사용 | 6.4, 7.4, 9.1, 9.3 |
| 4 | CSV 전체 덮어쓰기, 파일 잠금 없음 | 동시 저장 시 한쪽 변경 유실, 저장 중 장애 시 파일 손상 | DB로 이전 | 1장, 12.5 |
| 5 | VBLOCK 비용 차감이 `vessels_used`가 있는 행에는 적용되지 않음 | Ambr15 비용 과다 계상 | `vessels_used − 겹치는 VBLOCK 수` 등 규칙을 확정 | 10.3 |
| 6 | 기간별 비용을 일할 계산하지 않음 | 월 합계에 중복 집계 | 일할 계산 또는 "시작월 귀속" 같은 규칙 확정 | 10.4 |
| 7 | 비용에는 Ambr15, Ambr250, 2L, 200L만 포함 (5L, 10L, 50L, Wave의 N-stage는 0) | 의도인지 확인 필요 | 단가표에 scale을 추가하면 자동 포함되도록 설계 | 10.2 |
| 8 | 단가표가 코드에 하드코딩. `배치_단가.csv` 로더는 쓰이지 않음 | 단가를 바꾸려면 배포가 필요 | 관리자가 편집하는 테이블로 | 10.1 |
| 9 | 샌드박스 이동 시 `booking_id`가 바뀜 | 이력 추적 단절 | ID를 유지하고 변경 이력은 별도 테이블에 기록 | 12.3 |
| 10 | 샌드박스 클라이언트는 "완전히 감싸는" 경우만 드롭을 거부, 서버 이동은 검사 없음 | 겹침은 적용 시점에야 발견됨 | 의도된 설계(초안 단계에서는 겹침 허용)라면 유지. 다만 화면에 겹침을 표시 | 12.3 |
| 11 | 사용자 식별이 자유 텍스트 (`user` 파라미터, SME 이름) | 사칭 가능. SME 이름 표기가 제각각 | 로그인 세션에서 식별. SME는 사용자 목록에서 선택 | 12.2, 13장 |
| 12 | 비용 페이지와 `/admin/shutdown`에 인증 없음, CORS `*` | 정보 노출, 서비스 중단 | 인증 적용 | 12.6, 13장 |
| 13 | 감사 로그를 관리자가 삭제할 수 있고, 복원 시 실행자가 `'Admin'` 고정 | 감사 추적 신뢰도 낮음 | 추가만 가능한(append-only) 로그, 실제 사용자 기록 | 9.2 |
| 14 | Import "Skip" 모드는 파일 내부 행끼리 충돌을 검사하지 않음. Replace All은 백업 없음 | 데이터 손상 위험 | 내부 충돌 검사, 교체 전 자동 백업 | 9.3 |
| 15 | 관리자 Method 선택지에 `Perfusion`, `N/A`가 없음 | N-1 Perfusion 행이나 블록 행을 편집하면 값이 바뀌거나 검증 오류 | 선택지를 단일 상수로 관리 | 9.1 |
| 16 | Forward 모드에는 과거 날짜 검사가 없음 (Reverse에만 있음) | 과거 예약이 생성될 수 있음 | 두 모드에 같은 규칙 적용 | 6.2 |
| 17 | 공휴일이 2025–2027년만 하드코딩 | 2028년부터 표시 누락 | 공휴일 테이블 또는 외부 API | 11.3 |
| 18 | 설비 목록이 코드 상수 | 설비 추가나 폐기에 배포가 필요. `status` 필드는 쓰이지 않음 | 설비 마스터 테이블 + 활성 상태 | 3장 |
| 19 | `booking_id` 접두어로 블록 종류를 구분 | 문자열 규칙에 의존 | `kind` 필드 분리 | 2.2 |
| 20 | 위저드 체크박스 라벨 `털들 배양기 포함` | 의미 불명확 (오타로 보임) | 업무 담당자에게 정확한 명칭 확인 | 5장 |

---

## 15. 부록: 상수 표

### 15.1 Scale별 Method 선택지 (`utils.py:266`, `App.jsx` `METHOD_OPTIONS`)

| Scale | Method |
|---|---|
| Ambr15 | Fed-batch |
| Ambr250 | EFB, iEFB, EN1 |
| 2L, 5L, 10L, 50L, 200L | Fed-batch, EFB, iEFB, N1, EN1 |
| Wave | Fed-batch |

이 표는 **N stage에만** 적용된다. N-1은 `Fed-batch / Perfusion`, 나머지 stage는 `Fed-batch` 고정이다 (6.1).

### 15.2 단가표 (KRW / vessel, `1_Cost.py:13`)

| Scale | Fed-batch | EFB | iEFB | N1 | EN1 |
|---|---:|---:|---:|---:|---:|
| Ambr15 | 267,915 | – | – | – | – |
| Ambr250 | – | 1,239,045 | 1,392,776 | – | 1,620,680 |
| 2L | 1,211,714 | 1,268,641 | 1,436,718 | 2,166,611 | 2,238,964 |
| 200L | 26,891,157 | 33,645,055 | 27,318,015 | 76,861,560 | 79,701,514 |

### 15.3 기타 상수

| 이름 | 값 | 위치 |
|---|---|---|
| 샌드박스 잠금 유휴 만료 | 30분 | `main.py` |
| 되돌리기 최대 단계 | 50 | `main.py` |
| 적용 실패 제한 | IP당 5분 안에 5회 | `main.py` |
| 자동 백업 보관 수 | 10 | `utils.py:783` |
| 로그인 잠금 | 5회 실패 → 5분 | `auth.py` |
| 로그인 유휴 만료 | 1시간 | `auth.py` |
| PBKDF2 반복 횟수 | 200,000 | `auth.py`, `auth_utils.py` |
| 샌드박스 포트 | 8561 | `_sandbox_server.py` |
| React Gantt 1일 폭 | 22px | `Gantt.jsx` |

### 15.4 원본에서 그대로 가져가야 할 상수

다음 표는 길어서 이 문서에 옮기지 않았다. 원본 파일에서 그대로 복사하면 된다.

- `PROJECT_BG_MAP`, `PROJECT_FONT_MAP` — 제품별 Gantt 색상 (`utils.py:21–49`)
- `REACTOR_EQ_MAP` — 배양기 ID → 사내 EQ 번호 (`utils.py:90–133`)
- `KR_HOLIDAYS` — 2025–2027 한국 공휴일 (`utils.py:501–536`)
- `INVENTORY_CONFIGS` — 설비 정의 (`utils.py:51–88`)
