import cv2
import numpy as np
import requests
from flask import Flask, jsonify, request
import threading
import os
from time import sleep

app = Flask(__name__)

# 현재 x1 값을 저장할 변수
current_x1 = 0

# x1 값을 반환하는 GET 엔드포인트
@app.route('/x1', methods=['GET'])
def get_x1():
    print(current_x1)
    return jsonify({'x1': current_x1})

# opencv를 동작시키는 GET 엔드포인트
@app.route('/books1', methods=['GET'])
def get_books1():
    # 새로운 쓰레드에서 suntracking 함수 실행
    thread = threading.Thread(target=suntracking)
    thread.start()
    return '', 204

# current_x1을 초기화 시키는 GET 엔드포인트
@app.route('/reset_x1', methods=['GET'])
def reset_x1():
    global current_x1
    current_x1 = 0
    return jsonify({'status': 'x1 reset to 0'})

# opencv 함수
def suntracking():
    global current_x1
    print("SUNTRACKING")
    # 비디오 캡처 객체 생성
    cap = cv2.VideoCapture('annesa1.mp4')


    if not cap.isOpened():
        print("Error opening video file")
        return

    # 배경 제거 객체 생성
    fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)

    frame_count = 0

    # output_folder = 'captured_images'
    # os.makedirs(output_folder, exist_ok=True)  # 폴더가 없으면 생성

    while cap.isOpened():
        x1 = 0
        ret, frame = cap.read()
        if not ret:
            # current_x1 = -1
            # break
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue  # 다음 반복으로 넘어감

        # 배경 제거 적용하여 모션 감지
        fgmask = fgbg.apply(frame)

        # 잡음 제거를 위한 이진화 및 모폴로지 연산
        _, thresh = cv2.threshold(fgmask, 244, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # 윤곽선 검출
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected = False

        for contour in contours:
            # 작은 잡음을 무시하기 위한 조건
            if cv2.contourArea(contour) < 500:
                continue
            # 객체에 사각형 그리기
            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            detected = True
            if 0 <= x < 286:
                current_x1 = 1

            elif 286 <= x < 572:
                current_x1 = 2

            elif 572 <= x < 858:
                current_x1 = 4

            elif 858 <= x < 1144:
                current_x1 = 32

            else:
                current_x1 = 64
        # 객체가 감지되지 않았다면 current_x1을 0으로 설정
        if not detected:
            current_x1 = 0
        # 결과 출력
        cv2.imshow('Motion Detection', frame)
        # 전체 이미지 캡처 및 저장
        # cv2.imwrite(os.path.join(output_folder, 'captured_image.jpg'), frame)  # 특정 폴더에 전체 프레임 저장
        # cv2.imwrite(os.path.join(output_folder, f'{frame_count}.jpg'), frame)  # 특정 폴더에 전체 프레임 저장
        # frame_count += 1  # 프레임 카운터 증가
        sleep(0.01)
        # 'q' 키를 누르면 종료
        if cv2.waitKey(1) & 0xFF == ord('q'):
            current_x1 = -1
            break

    cap.release()
    cv2.destroyAllWindows()


# Video play control variables
is_playing = False
speed_factor = 2.0

# 모든 책 목록 조회
books = [{"size": "L", "count": 0}, {"size": "S", "count": 0}]

@app.route('/books', methods=['GET'])
def get_books():
    return jsonify(books)

@app.route('/set_speed', methods=['POST'])
def set_speed():
    global speed_factor
    data = request.get_json()
    speed_factor = data.get('speed', 1.0)
    return jsonify({'speed_factor': speed_factor}), 200

# WPF에 알림 보내는 함수
def notify_wpf():
    try:
        response = requests.post('http://localhost:8080/', json={"message": "PUT 요청 성공"})
        if response.status_code == 200:
            print("WPF 알림 성공")
        else:
            print(f"WPF 알림 실패: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"WPF로 알림 실패: {e}")

@app.route('/books/update_count', methods=['PUT'])
def update_book_count():
    data = request.get_json()
    size = data.get("size")

    book = next((b for b in books if b["size"] == size), None)
    if book:
        book["count"] += 1
        notify_wpf()  # WPF로 PUT 요청 성공 후 알림
        return jsonify(book), 200

    return jsonify({'error': 'Size not found'}), 404

@app.route('/video/start', methods=['POST'])
def start_video():
    global is_playing
    is_playing = True
    return jsonify({'status': 'started'}), 200

@app.route('/video/stop', methods=['POST'])
def stop_video():
    global is_playing
    is_playing = False
    return jsonify({'status': 'stopped'}), 200

def run_flask():
    app.run(debug=True, use_reloader=False)

def run_opencv():
    global speed_factor, is_playing

    video = cv2.VideoCapture('box.mp4')
    fps = video.get(cv2.CAP_PROP_FPS)
    delay = int(1000 / fps)

    size_count = {'S': 0, 'L': 0}
    detected_boxes = []
    frame_counter = {}

    frame_threshold = 7

    while True:
        if is_playing:
            ret, frame = video.read()
            if not ret:
                video.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lower_brown = np.array([10, 100, 20])
            upper_brown = np.array([20, 255, 255])
            mask = cv2.inRange(hsv, lower_brown, upper_brown)
            mask = cv2.GaussianBlur(mask, (5, 5), 0)
            edges = cv2.Canny(mask, 50, 500)

            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            current_boxes = []

            for contour in contours:
                area = cv2.contourArea(contour)
                if 2000 < area < 30000:
                    x, y, w, h = cv2.boundingRect(contour)
                    current_boxes.append((x, y, w, h))

                    count_label = 'L' if area >= 6000 else 'S'

                    found = False
                    for detected in detected_boxes:
                        detected_x, detected_y, detected_w, detected_h = detected
                        detected_center = (detected_x + detected_w // 2, detected_y + detected_h // 2)
                        current_center = (x + w // 2, y + h // 2)

                        distance = np.sqrt((detected_center[0] - current_center[0]) ** 2 +
                                           (detected_center[1] - current_center[1]) ** 2)

                        if distance < 50:
                            found = True
                            break

                    if not found:
                        size_count[count_label] += 1
                        detected_boxes.append((x, y, w, h))
                        frame_counter[(x, y, w, h)] = 0
                    else:
                        index = detected_boxes.index(detected)
                        detected_boxes[index] = (x, y, w, h)
                        frame_counter[(x, y, w, h)] = 0

            for detected in detected_boxes[:]:
                detected_x, detected_y, detected_w, detected_h = detected
                detected_center = (detected_x + detected_w // 2, detected_y + detected_h // 2)

                if not any(np.sqrt((detected_center[0] - (x + w // 2)) ** 2 +
                                   (detected_center[1] - (y + h // 2)) ** 2) < 50
                           for x, y, w, h in current_boxes):
                    frame_counter[detected] += 1
                    if frame_counter[detected] >= frame_threshold:
                        detected_boxes.remove(detected)
                        del frame_counter[detected]
                        data = {'size': 'L' if (detected_w * detected_h) >= 6000 else 'S'}
                        requests.put('http://127.0.0.1:5000/books/update_count', json=data)

            for detected in detected_boxes:
                x, y, w, h = detected
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                label = 'L' if (w * h) >= 6000 else 'S'
                cv2.putText(frame, label, (x + 10, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)

            cv2.imshow('Detected Boxes', frame)

            adjusted_delay = int(delay / speed_factor)
            if cv2.waitKey(adjusted_delay) & 0xFF == ord('q'):
                break
        else:
            sleep(0.1)

    video.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    opencv_thread = threading.Thread(target=run_opencv)
    opencv_thread.start()
