import sys
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop

# 기본 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class KiwoomAuth:
    """
    키움증권 OpenAPI 공식 메뉴얼 기반 독립 접속 모듈
    (32비트 Python 환경 필수)
    """
    def __init__(self):
        # 키움 OpenAPI는 PyQt의 QApplication 이벤트 루프 내에서만 동작
        self.app = QApplication(sys.argv)
        
        # 공식 제공 OCX 컨트롤 호출 (레지스트리에 등록된 키움 OpenAPI)
        try:
            self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        except Exception as e:
            logging.error(f"키움 OpenAPI 모듈을 불러오지 못했습니다. (32비트 파이썬 및 OpenAPI 설치 확인 필요) 에러: {e}")
            sys.exit(1)
        
        # 이벤트 슬롯 연결 (로그인 결과 수신)
        self.kiwoom.OnEventConnect.connect(self.on_event_connect)
        
        self.login_event_loop = QEventLoop()

    def connect_account(self):
        """
        키움증권 로그인 창을 띄우고, 완료될 때까지 대기합니다.
        공식 함수: CommConnect()
        """
        logging.info("키움증권 로그인 요청 중...")
        
        # 0을 리턴하면 정상 호출, 음수면 실패
        ret = self.kiwoom.dynamicCall("CommConnect()")
        if ret != 0:
            logging.error(f"CommConnect() 호출 실패 (에러코드: {ret})")
            sys.exit(1)
            
        # 로그인이 완료(on_event_connect 호출)될 때까지 이벤트 루프 대기
        self.login_event_loop.exec_()

    def on_event_connect(self, err_code):
        """
        로그인 결과 이벤트 콜백
        err_code == 0 이면 정상, 그 외는 에러
        """
        if err_code == 0:
            logging.info("키움증권 로그인 성공!")
            
            # GetLoginInfo() 함수로 계좌번호 가져오기
            account_num = self.kiwoom.dynamicCall("GetLoginInfo(\"ACCNO\")")
            # 계좌번호는 ';' 로 구분된 문자열이므로 파싱
            accounts = account_num.strip(';').split(';')
            
            logging.info(f"보유 계좌 목록: {accounts}")
            if accounts:
                logging.info(f"기본 사용 계좌: {accounts[0]}")
        else:
            logging.error(f"키움증권 로그인 실패 (에러코드: {err_code})")
        
        # 이벤트 루프 종료하여 다음 코드로 진행되게 함
        self.login_event_loop.exit()

if __name__ == "__main__":
    # 독립 스크립트 실행 테스트
    auth = KiwoomAuth()
    auth.connect_account()
    
    # 윈도우 창이 바로 닫히지 않도록 이벤트 루프 유지 (서버용)
    # sys.exit(auth.app.exec_())
