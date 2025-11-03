import asyncio
from ultralytics import YOLO  # pylint: disable=no-name-in-module
import cv2
import os
from dotenv import load_dotenv
import time
import numpy as np

from util import (
    read_license_plate,
    write_log_entry,
    is_string_similar_to_any_in_list,
)

from meross_controller import MerossGarageController

load_dotenv()

rtsp_url = os.getenv("RTSP_URL")

LPR_PROCESSING_INTERVAL = 10  # seconds


# load models
coco_model = YOLO("yolov8n.pt")
license_plate_detector = YOLO("license_plate_detector.pt")

# car, truck, bus, motorcycle
vehicles = [2, 3, 5, 7]
license_plate_whitelist = []
CSV_HEADER = ["time", "license_number", "license_number_score", "open"]



def save_frame_to_jpg(
    frame_to_save, output_folder: str, filename_prefix: str = "frame"
):
    """
    将给定的图像帧保存为 JPG 文件。

    参数:
    frame_to_save: 要保存的 OpenCV 图像帧 (NumPy 数组)。
    output_folder: 用于保存 JPG 文件的文件夹路径。
    filename_prefix: 保存的 JPG 文件名的前缀。

    返回:
    bool: 如果保存成功则为 True，否则为 False。
    str: 如果保存成功，则为完整的文件路径，否则为 None。
    """
    if frame_to_save is None:
        print("错误：没有提供有效的帧进行保存。")
        return False, None

    try:
        # 如果输出文件夹不存在，则创建它
        if not os.path.exists(output_folder):
            os.makedirs(output_folder, exist_ok=True)
            print(f"已创建输出文件夹: {output_folder}")
    except OSError as e:
        print(f"错误：创建输出文件夹 {output_folder} 失败: {e}")
        return False, None

    # 生成一个基于时间戳的唯一文件名
    timestamp = time.strftime("%Y%m%d_%H%M%S_%f")  # %f 用于毫秒，确保更高唯一性
    file_name = f"{filename_prefix}_{timestamp}.jpg"
    full_file_path = os.path.join(output_folder, file_name)

    try:
        # 保存帧为 JPG 文件
        # 您可以设置 JPEG 图像质量 (0-100，越高图像质量越好，文件越大)
        # params = [cv2.IMWRITE_JPEG_QUALITY, 90] # 例如，质量设置为 90
        # success = cv2.imwrite(full_file_path, frame_to_save, params)
        success = cv2.imwrite(full_file_path, frame_to_save)  # 使用默认质量

        if success:
            print(f"帧已成功保存为: {full_file_path}")
            return True, full_file_path
        else:
            print(f"错误：保存帧到 {full_file_path} 失败 (cv2.imwrite 返回 False)。")
            return False, None
    except Exception as e:
        print(f"保存帧时发生异常: {e}")
        return False, None


def initialize_capture(rtsp_url: str):
    """
    初始化并返回一个 VideoCapture 对象。
    如果失败则返回 None。
    """
    print(f"正在连接到 RTSP 流: {rtsp_url} ...")
    # 可选: 尝试为RTSP强制使用TCP传输 (某些OpenCV后端和网络环境下更稳定)
    # os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)  # 尝试指定FFMPEG后端

    if not cap.isOpened():
        print(f"错误: 无法打开 RTSP 流位于 {rtsp_url}")
        # 可以在这里添加更详细的错误检查提示
        return None

    print("成功连接到 RTSP 流。")
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(
        f"视频流属性: {width}x{height} @ {fps if fps > 0 else 'N/A'} FPS (摄像头报告值)"
    )
    return cap

# Global controller instance to maintain state
_controller = None

async def open_garage_door():
    global _controller
    
    email = os.environ.get("MEROSS_EMAIL") 
    password = os.environ.get("MEROSS_PASSWORD")
    device_name = os.environ.get("MEROSS_GARAGE_DOOR_NAME") 

    if not email or not password or not device_name:
        return -10

    # Reuse existing controller or create new one
    if _controller is None:
        _controller = MerossGarageController(email=email, password=password, device_name=device_name)
    
    try:
        if await _controller.initialize():
            opened = await _controller.open_door()
            # Don't close connection to maintain state
            if opened:
                return 1
            else:
                return 0  # Cooldown or other failure
        else:
            return -1
    except Exception as e:
        print(f"Session error, resetting controller: {e}")
        # Reset controller on session errors
        if _controller:
            try:
                await _controller.close_connection()
            except:
                pass
        _controller = None
        return -1


async def process_frame_for_lpr(
    frame, frame_capture_time_str, output_crop_dir, output_crop_thresh_dir
):
    print(f"处理帧: {frame_capture_time_str}")
    # read frames
    # detect vehicles
    detections = coco_model(frame)[0]
    detect_results = []
    for detection in detections.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = detection
        if int(class_id) in vehicles:
            detect_results.append([x1, y1, x2, y2, score])

    # track vehicles
    detect_results_array = (
        np.asarray(detect_results) if len(detect_results) > 0 else np.empty((0, 5))
    )

    # detect license plates
    license_plates = license_plate_detector(frame)[0]
    for license_plate in license_plates.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = license_plate

        license_plate_crop = frame[int(y1) : int(y2), int(x1) : int(x2), :]

        # process license plate
        license_plate_crop_gray = cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2GRAY)
        _, license_plate_crop_thresh = cv2.threshold(
            license_plate_crop_gray, 64, 255, cv2.THRESH_BINARY_INV
        )
        # Save the thresholded crop

        # read license plate number
        license_plate_text, license_plate_text_score = read_license_plate(
            license_plate_crop_thresh
        )
        if license_plate_text is not None:
            door_open = 0
            if is_string_similar_to_any_in_list(
                license_plate_text, license_plate_whitelist, 80
            ):
                # leave evidence
                crop_thresh_filename = os.path.join(
                    output_crop_thresh_dir,
                    f"{frame_capture_time_str}_car_thresh.png",
                )
                cv2.imwrite(crop_thresh_filename, license_plate_crop_thresh)
                # open the garage door
                door_open = await open_garage_door()
            if door_open == 1:
                data_row = [
                    frame_capture_time_str,
                    license_plate_text,
                    license_plate_text_score,
                    door_open,
                ]
                write_log_entry(data_row, CSV_HEADER)


async def main():

    output_crop_dir = "./license_plate_crops"
    if not os.path.exists(output_crop_dir):
        os.makedirs(output_crop_dir)

    output_crop_thresh_dir = "./license_plate_crops_thresh"
    if not os.path.exists(output_crop_thresh_dir):
        os.makedirs(output_crop_thresh_dir)

    if not rtsp_url:
        print("错误: RTSP_URL 环境变量未设置。")
        return

    cap = initialize_capture(rtsp_url)
    if cap is None:
        print("错误: 无法初始化视频捕获。")
        return
    print("Connected to RTSP stream successfully.")

    last_lpr_processed_time = time.monotonic()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("错误: 无法读取视频帧。")
                print("Reconnecting after 5s...")
                time.sleep(5)
                cap.release()
                cap = initialize_capture(rtsp_url)
                if cap is None:
                    print("错误: 无法重新连接到视频流。")
                    break
                print("Reconnected to RTSP stream successfully.")
                last_lpr_processed_time = time.monotonic()
                continue

            current_time_monotonic = time.monotonic()
            current_time_display_str = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime()
            )

            if (
                current_time_monotonic - last_lpr_processed_time
            ) >= LPR_PROCESSING_INTERVAL:
                # rotate the frame 90 degrees
                frame_rotated = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                try:
                    await process_frame_for_lpr(
                        frame_rotated.copy(),
                        current_time_display_str,
                        output_crop_dir,
                        output_crop_thresh_dir,
                    )
                except Exception as e:
                    # write error into log.txt
                    with open("log.txt", "a") as f:
                        f.write(
                            f"{current_time_display_str} Error processing frame: {e}\n"
                        )
                finally:
                    last_lpr_processed_time = current_time_monotonic

    except KeyboardInterrupt:
        print("用户中断，退出程序。")
    finally:
        if cap:
            cap.release()
        print("program terminated.")


if __name__ == "__main__":
    asyncio.run(main())
