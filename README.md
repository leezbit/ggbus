# GGBus (경기도 버스 도착정보) Home Assistant 통합구성요소

경기도 버스도착정보 API와 정류소 조회 API(모두 data.go.kr 공공 API)를 사용해 **정류장 단위로 버스 도착정보를 90초 간격으로 갱신**하는 HACS 커스텀 통합입니다.

## 기능

- HACS로 설치 가능한 커스텀 통합
- 초기 등록 시:
  - 공공데이터포털 API 서비스키 입력
  - 정류장 번호(5자리) 입력
  - 해당 정류장의 버스 노선 목록 조회 후 선택
- 등록 후:
  - 정류장 장치(device) 아래에 버스 노선별 하위 기기(device)를 만들고, 각 버스 기기마다 항목별 엔티티 생성(도착예정/남은정류장/운행상태/저상여부 sensor 제공)
  - 버스 하위 기기에서 "기기 제거"를 눌러 해당 노선만 삭제 가능
- API 호출 제한(일 1,000회)을 고려해 **정류장당 기본 1회/90초** 폴링 (전 노선 미운행 시 20분 간격)
- 정류장 기기에 `API 상태` 센서를 추가해 최근 오류/성공 시각 확인 가능
- 저상버스/도착정보 표시는 data.go.kr 원본 응답 기준으로 표시됨 (다른 앱과 표시 시점/기준이 다를 수 있음)

## 설치

1. 이 저장소를 본인 GitHub에 푸시
2. HACS > Integrations > 메뉴 > Custom repositories
3. Repository URL 입력 후 Category는 `Integration`
4. `GGBus Home Assistant Integration` 설치
5. Home Assistant 재시작

## 사용

1. 설정 > 기기 및 서비스 > 통합 추가
2. `Gyeonggi Bus Stop Arrivals` 선택
3. API 서비스키 + 정류장번호(5자리) 입력
4. 노선 목록에서 표시할 버스 선택

## API

- 경기도_버스도착정보 조회: <https://www.data.go.kr/data/15080346/openapi.do>
- 경기도_정류소 조회: <https://www.data.go.kr/data/15080666/openapi.do>
