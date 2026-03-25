# GGBus (경기도 버스 도착정보) Home Assistant 통합구성요소 🚍

경기도 버스 도착정보 Open API (data.go.kr)를 기반으로,
**정류장 단위 버스 도착 정보를 Home Assistant에서 확인할 수 있는 HACS 커스텀 통합입니다.**

---

## ✨ 주요 기능

* HACS를 통한 간편 설치
* 정류장 번호(5자리) 기반 버스 도착정보 조회
* 노선별 센서 자동 생성
* 정류장 단위 디바이스 + 노선별 하위 디바이스 구조
* 90초 간격 자동 갱신 (전 노선 미운행 시 20분 간격)
* API 상태 센서 제공 (최근 성공/오류 시각)
* 저상버스 여부 및 운행 상태 표시

---

## 🧩 제공 엔티티

각 버스 노선별로 다음 센서가 생성됩니다:

* 도착 예정 시간
* 남은 정류장 수
* 운행 상태 (운행 중 / 운행 종료)
* 저상버스 여부

---

## 📦 설치 방법

### 1. HACS Custom Repository 등록

1. HACS → Integrations
2. 우측 상단 메뉴 (⋮) → **Custom repositories**
3. 아래 정보 입력:

* Repository URL: `https://github.com/<your-username>/<repo-name>`
* Category: `Integration`

4. 저장 후 목록에서 **GGBus** 검색 및 설치

---

### 2. Home Assistant 재시작

설치 후 반드시 Home Assistant를 재시작하세요.

---

## ⚙️ 사용 방법

1. 설정 → **기기 및 서비스**
2. **통합 추가**
3. `Gyeonggi Bus Stop Arrivals` 선택
4. 다음 정보 입력:

* 공공데이터포털 API 서비스키
* 정류장 번호 (5자리)

5. 조회된 노선 목록에서 원하는 버스 선택

---

## 🔧 노선 추가 / 삭제

* 이미 등록된 정류장은 **서비스 추가로 다시 등록할 수 없습니다**
* 버스 노선 추가/삭제는:

👉 **통합 → 해당 정류장 → 옵션(톱니바퀴)** 에서 변경하세요

---

## ⏱️ 업데이트 주기

* 기본: **90초**
* 전 노선 미운행 시: **20분**

(API 호출 제한을 고려한 설정)

---

## 🌐 사용 API

* [경기도 버스도착정보 조회](https://www.data.go.kr/data/15080346/openapi.do)
* [경기도 정류소 조회](https://www.data.go.kr/data/15080666/openapi.do)

---

## ⚠️ 주의사항

* API 응답 지연 또는 오류로 인해 실제 도착 정보와 차이가 발생할 수 있습니다
* 다른 앱(카카오버스, 네이버지도 등)과 표시 기준이 다를 수 있습니다
* 공공 API 특성상 서비스 안정성이 보장되지 않습니다

---

## ❗ Disclaimer

This integration is **not affiliated with or endorsed by Gyeonggi-do or data.go.kr**.

All data is provided by public APIs, and accuracy or availability is not guaranteed.
Use at your own risk.

---

## 📜 License

This project is licensed under the MIT License.

---

## 🙌 기여

이슈 및 PR은 언제든 환영합니다!
