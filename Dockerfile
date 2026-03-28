# 1. 베이스 이미지 설정 (Python 3.10 slim 버전)
FROM python:3.10-slim-bullseye

# 2. 필수 시스템 패키지 설치 (ffmpeg 포함)
# 수동으로 ffmpeg를 설치하는 가장 확실한 리눅스 표준 명령어입니다.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리 설정
WORKDIR /app

# 4. 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. 다운로드 폴더 생성 및 권한 설정
RUN mkdir -p downloads && chmod 777 downloads

# 7. 실행 환경 변수 설정
ENV PORT=10000

# 8. 서버 실행 (Gunicorn 사용)
# Render의 포트 환경 변수에 맞춰서 실행합니다.
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 youtubereserch:app
