#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 1. 필요한 모든 라이브러리 통합
import os
import re
import traceback
import json
import threading
import sys
from pathlib import Path
from queue import Queue

from flask import Flask, request, Response, stream_with_context, jsonify, send_file, send_from_directory
from flask_cors import CORS

import yt_dlp

try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
except ImportError:
    YouTubeTranscriptApi = None

# 2. Flask 앱 초기화
app = Flask(__name__)
CORS(app)

# 최대 업로드 파일 크기 설정 (500MB)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

# 3. 기본 설정

# PyInstaller로 빌드된 exe인지 여부에 따라 BASE_DIR 다르게 설정
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    # exe로 실행 중일 때: 실행 파일이 있는 폴더 기준
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    # .py로 실행 중일 때
    BASE_DIR = Path(__file__).resolve().parent

DEFAULT_DOWNLOAD_DIR = BASE_DIR / "downloads"
DEFAULT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 디버그용으로 한 번 찍어보면 좋음
print("========================================")
print("[TubeResearch] 서버 시작 업데이트 버전 v1.0.1")
print(f"[TubeResearch] BASE_DIR = {BASE_DIR}")
print(f"[TubeResearch] DOWNLOAD_DIR = {DEFAULT_DOWNLOAD_DIR}")
print("========================================")

# --- 4. 영상 다운로드 기능 (정상 동작하므로 변경 없음) ---

def build_subtitle_opts(embed_into_video: bool):
    if embed_into_video:
        return { "writesubtitles": True, "writeautomaticsub": True, "subtitlesformat": "best", "postprocessors": [{"key": "FFmpegEmbedSubtitle"}] }
    return { "writesubtitles": True, "writeautomaticsub": True, "skip_download": True, "subtitlesformat": "vtt" }

def make_ydl_opts_base(save_dir: Path):
    return {
        "outtmpl": str(save_dir / "%(id)s.%(ext)s"),
        "quiet": False,
        "verbose": True,
        "noprogress": False,
        "ignoreerrors": False, # 에러 발생 시 None 반환 방지
        "nocheckcertificate": True,
        "concurrent_fragment_downloads": 3,
        "format": "bv*+ba/b",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "referer": "https://www.google.com/",
    }

@app.route("/download", methods=["POST"])
def api_download_stream():
    data = request.get_json(force=True, silent=True) or {}
    url = data.get("url")
    mode = (data.get("mode") or "both").lower()
    save_dir = DEFAULT_DOWNLOAD_DIR
    if not url: return Response(json.dumps({"error": "URL이 비어 있습니다."}), status=400, mimetype='application/json')
    def generate_progress():
        yield f"data: {json.dumps({'status': 'progress', 'percent': 0, 'message': '다운로드를 초기화하고 있습니다...'})}\n\n"
        q = Queue()
        def queue_progress_hook(d): q.put(d)
        ydl_opts = make_ydl_opts_base(save_dir)
        ydl_opts["progress_hooks"] = [queue_progress_hook]
        ydl_opts["merge_output_format"] = "mp4"
        if mode in ("both", "subs"):
            sub_opts = build_subtitle_opts(embed_into_video=(mode == "both")); ydl_opts.update(sub_opts)
            base_pps = ydl_opts.get("postprocessors", []); sub_pps = sub_opts.get("postprocessors", [])
            ydl_opts["postprocessors"] = base_pps + sub_pps
        if mode == "subs": ydl_opts["skip_download"] = True
        def download_thread_func():
            try:
                print(f"[Debug] YT-DLP 시작: {url}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    # 실제 저장된 파일명 추출 (확장자 포함)
                    if info:
                        video_id = info.get('id')
                        ext = info.get('ext')
                        filename = f"{video_id}.{ext}"
                        print(f"[Debug] 실제 저장된 파일명: {filename}")
                        q.put({'status': 'final_ok', 'filename': filename})
                    else:
                        q.put({'status': 'final_ok'})
                print("[Debug] YT-DLP 완료")
            except Exception as e:
                print(f"[Debug] YT-DLP 오류 발생: {str(e)}")
                traceback.print_exc()
                q.put({'status': 'final_error', 'error': str(e)})
        download_thread = threading.Thread(target=download_thread_func)
        download_thread.daemon = True # 서버 종료 시 함께 종료되도록 설정
        download_thread.start()
        print("[Debug] 다운로드 스레드 시작됨")
        while True:
            d = q.get()
            print(f"[Debug] 큐 데이터 수신: {d.get('status')}")
            if d.get('status') == 'final_ok': 
                filename = d.get('filename', '')
                yield f"data: {json.dumps({'status': 'ok', 'percent': 100, 'message': '성공적으로 다운로드 및 처리되었습니다.', 'filename': filename})}\n\n"
                break
            if d.get('status') == 'final_error': error_msg = '오류 발생: ' + str(d.get('error', '')); yield f"data: {json.dumps({'status': 'error', 'message': error_msg})}\n\n"; break
            status = d.get('status')
            if status == 'downloading':
                percent_str = d.get('_percent_str', '0.0%').strip().replace('\x1b[0;94m', '').replace('\x1b[0m', '')
                try: percent = float(percent_str.replace('%',''))
                except ValueError: percent = 0.0
                speed_str = f"{d.get('_speed_str', 'N/A')}".strip()
                yield f"data: {json.dumps({'status': 'progress', 'percent': percent, 'message': f'다운로드 중: {percent_str} ({speed_str})'})}\n\n"
            elif status == 'finished': yield f"data: {json.dumps({'status': 'progress', 'percent': 100, 'message': '다운로드 완료, 파일을 처리하고 있습니다...'})}\n\n"
            elif status == 'error': yield f"data: {json.dumps({'status': 'error', 'message': '다운로드 중 오류가 발생했습니다.'})}\n\n"
    return Response(stream_with_context(generate_progress()), mimetype='text/event-stream')


# --- 5. 자막 추출 기능 (공식 문서 기반으로 재작성 및 안정화) ---

def extract_video_id(url: str) -> str | None:
    patterns = [r'(?:v=|/)([0-9A-Za-z_-]{11}).*', r'(?:embed/)([0-9A-Za-z_-]{11})', r'(?:youtu\.be/)([0-9A-Za-z_-]{11})']
    for p in patterns:
        m = re.search(p, url)
        if m: return m.group(1)
    if len(url) == 11 and re.match(r'^[0-9A-Za-z_-]{11}$', url): return url
    return None

@app.route("/transcript")
def api_transcript():
    video_url_or_id = request.args.get("video", "").strip()
    video_id = extract_video_id(video_url_or_id)
    
    if not video_id:
        return jsonify({"error": "유효하지 않은 YouTube 주소 또는 영상 ID입니다."}), 400

    if YouTubeTranscriptApi is None:
        return jsonify({"error": "자막 추출 라이브러리(youtube_transcript_api)가 설치되지 않았습니다."}), 500

    try:
        # 자막 목록을 먼저 가져오고 가장 적합한 자막(ko, en)을 선택
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['ko', 'en'])
        transcript_data = transcript.fetch()
        
        # 데이터는 딕셔너리 리스트이므로 snippet['text'] 로 접근
        lines = [snippet['text'].strip() for snippet in transcript_data if snippet.get('text', '').strip()]
        
        if not lines:
             raise NoTranscriptFound("자막 내용이 비어 있습니다.")

        return jsonify({"lines": lines})

    except NoTranscriptFound:
        try:
            # 위에서 이미 transcript_list를 가져왔을 수 있으므로 재사용하거나 새로 가져옴
            try:
                if 'transcript_list' not in locals():
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            except:
                return jsonify({"error": "이 영상에는 자막이 없습니다."}), 404

            for transcript in transcript_list:
                if transcript.is_translatable:
                    translated_transcript = transcript.translate('ko').fetch()
                    lines = [snippet['text'].strip() for snippet in translated_transcript if snippet.get('text', '').strip()]
                    return jsonify({"lines": lines})
            
            # 번역할 자막조차 없는 최종적인 경우
            return jsonify({"error": "이 영상에는 한국어로 보거나 번역할 수 있는 자막이 없습니다."}), 404
        except Exception as e_trans:
            return jsonify({"error": f"자막 번역 중 오류가 발생했습니다: {e_trans}"}), 500
            
    except TranscriptsDisabled:
        return jsonify({"error": "이 영상은 자막 기능이 비활성화되어 있습니다."}), 403

    except Exception as e:
        app.logger.error(f"자막 처리 중 알 수 없는 오류 ({video_id}): {traceback.format_exc()}")
        return jsonify({"error": f"자막 처리 중 예상치 못한 오류 발생: {e}"}), 500


# --- 6. MP4 to MP3 변환 기능 ---

@app.route("/convert", methods=["POST"])
def convert_mp4_to_mp3():
    if 'file' not in request.files:
        return jsonify({"error": "파일이 없습니다."}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "선택된 파일이 없습니다."}), 400

    # 안전한 파일명 생성
    import uuid
    import subprocess
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wav', '.m4a', '.aac', '.ogg'):
         return jsonify({"error": "지원하지 않는 영상/음성 형식입니다."}), 400

    temp_id = str(uuid.uuid4())
    input_path = DEFAULT_DOWNLOAD_DIR / f"{temp_id}_input{ext}"
    output_path = DEFAULT_DOWNLOAD_DIR / f"{temp_id}.mp3"

    try:
        file.save(str(input_path))
        print(f"[Convert] 파일 저장됨: {input_path}")
        
        # FFmpeg를 사용하여 MP3로 변환
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-vn', '-acodec', 'libmp3lame', '-q:a', '2',
            '-y', str(output_path)
        ]
        
        print(f"[Convert] 변환 시작: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"[Convert] FFmpeg 오류: {result.stderr}")
            return jsonify({"error": f"변환 중 오류 발생: {result.stderr}"}), 500
        
        print(f"[Convert] 변환 완료: {output_path}")
        
        # 원본 파일 삭제
        if input_path.exists():
            os.remove(input_path)
            
        return send_file(
            str(output_path),
            mimetype="audio/mpeg",
            as_attachment=True,
            download_name=f"{os.path.splitext(file.filename)[0]}.mp3"
        )
    except Exception as e:
        print(f"[Convert] 시스템 오류: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": f"시스템 오류: {str(e)}"}), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "파일 크기가 너무 큽니다. (최대 500MB)"}), 413

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "서버 내부 오류가 발생했습니다."}), 500

@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/api/') or request.path in ['/convert', '/download', '/transcript', '/download_file']:
        return jsonify({"error": "요청하신 경로를 찾을 수 없습니다."}), 404
    
    # index.html 파일이 실제로 존재할 때만 전송 (재귀 방지)
    if (BASE_DIR / 'index.html').exists():
        return send_from_directory(BASE_DIR, 'index.html')
    return jsonify({"error": "페이지를 찾을 수 없습니다."}), 404

# --- 7. 기본 라우트 및 서버 실행 ---

@app.route("/")
def index_page():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route("/download_file/<path:filename>")
def download_file_to_user(filename):
    """서버에 저장된 파일을 사용자 PC로 전송 (자동 다운로드용)"""
    return send_from_directory(DEFAULT_DOWNLOAD_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)