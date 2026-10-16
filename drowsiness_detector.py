"""
============================================================
AI DRIVER DROWSINESS DETECTION SYSTEM
============================================================

Laptop-only version.

Features:
- Real-time webcam monitoring
- MediaPipe Face Landmarker
- Eye Aspect Ratio (EAR)
- Automatic 5-second calibration
- Eye-closure drowsiness detection
- Face-loss detection
- Laptop speaker alarm using Windows winsound
- No Raspberry Pi
- No physical buzzer
- No pygame
- No alarm.wav required

Press Q to quit.
============================================================
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import math
import time
import winsound
import threading
import os


# ============================================================
# SETTINGS
# ============================================================

MODEL_FILE = "face_landmarker.task"

CAMERA_INDEX = 0

# Time used to learn your normal open-eye EAR
CALIBRATION_TIME = 5.0

# Eyes must remain closed for this long
# before drowsiness alarm starts
DROWSINESS_TIME = 2.0

# Face must disappear for this long
# before alarm starts
NO_FACE_TIME = 2.0

# Drowsiness threshold
#
# Example:
# Normal EAR = 0.30
# Threshold = 0.30 * 0.75 = 0.225
#
# Lower value = less sensitive
# Higher value = more sensitive
THRESHOLD_FACTOR = 0.75


# ============================================================
# CHECK MODEL FILE
# ============================================================

if not os.path.exists(MODEL_FILE):

    print()
    print("==============================================")
    print("ERROR: face_landmarker.task NOT FOUND")
    print("==============================================")
    print()
    print("Put face_landmarker.task in the same folder")
    print("as drowsiness_detector.py")
    print()

    input("Press Enter to exit...")

    raise SystemExit


# ============================================================
# WINDOWS LAPTOP ALARM
# ============================================================

alarm_running = False
alarm_thread = None


def alarm_sound():

    """
    Runs the warning sound repeatedly
    in a background thread.
    """

    global alarm_running

    while alarm_running:

        try:

            # High-pitched warning beep
            winsound.Beep(
                2000,
                400
            )

            # Small pause
            time.sleep(0.1)

            # Second beep
            if alarm_running:

                winsound.Beep(
                    1500,
                    400
                )

                time.sleep(0.1)

        except Exception:

            break


def alarm_start():

    """
    Start the laptop speaker alarm.
    """

    global alarm_running
    global alarm_thread

    # Don't create multiple alarm threads
    if alarm_running:

        return

    alarm_running = True

    alarm_thread = threading.Thread(
        target=alarm_sound,
        daemon=True
    )

    alarm_thread.start()


def alarm_stop():

    """
    Stop the laptop speaker alarm.
    """

    global alarm_running

    alarm_running = False


# ============================================================
# LOAD MEDIAPIPE MODEL
# ============================================================

print()
print("Loading MediaPipe model...")

try:

    base_options = python.BaseOptions(
        model_asset_path=MODEL_FILE
    )

    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        num_faces=1
    )

    detector = (
        vision.FaceLandmarker
        .create_from_options(
            options
        )
    )

except Exception as error:

    print()
    print("==============================================")
    print("ERROR LOADING MEDIAPIPE MODEL")
    print("==============================================")
    print()
    print(error)
    print()

    input("Press Enter to exit...")

    raise SystemExit


# ============================================================
# EYE LANDMARK POINTS
# ============================================================

# Right eye landmarks
RIGHT_EYE = [
    33,
    160,
    158,
    133,
    153,
    144
]

# Left eye landmarks
LEFT_EYE = [
    362,
    385,
    387,
    263,
    373,
    380
]


# ============================================================
# EYE ASPECT RATIO
# ============================================================

def calculate_ear(
    landmarks,
    eye_points,
    width,
    height
):

    """
    Calculate Eye Aspect Ratio.

    EAR high  = eye open
    EAR low   = eye closed
    """

    points = []

    for index in eye_points:

        x = landmarks[index].x * width
        y = landmarks[index].y * height

        points.append(
            (x, y)
        )

    p1, p2, p3, p4, p5, p6 = points

    # Vertical eye distances
    vertical_1 = math.dist(
        p2,
        p6
    )

    vertical_2 = math.dist(
        p3,
        p5
    )

    # Horizontal eye distance
    horizontal = math.dist(
        p1,
        p4
    )

    if horizontal == 0:

        return 0

    ear_value = (
        vertical_1 +
        vertical_2
    ) / (
        2 *
        horizontal
    )

    return ear_value


# ============================================================
# CALCULATE BOTH EYES
# ============================================================

def calculate_average_ear(
    landmarks,
    width,
    height
):

    right_ear = calculate_ear(
        landmarks,
        RIGHT_EYE,
        width,
        height
    )

    left_ear = calculate_ear(
        landmarks,
        LEFT_EYE,
        width,
        height
    )

    average_ear = (
        right_ear +
        left_ear
    ) / 2

    return (
        right_ear,
        left_ear,
        average_ear
    )


# ============================================================
# DRAW EYE LANDMARKS
# ============================================================

def draw_eye_points(
    frame,
    landmarks,
    eye_points,
    width,
    height
):

    for index in eye_points:

        x = int(
            landmarks[index].x *
            width
        )

        y = int(
            landmarks[index].y *
            height
        )

        cv2.circle(
            frame,
            (x, y),
            2,
            (0, 255, 0),
            -1
        )


# ============================================================
# OPEN WEBCAM
# ============================================================

print("Opening webcam...")

camera = cv2.VideoCapture(
    CAMERA_INDEX
)

if not camera.isOpened():

    print()
    print("==============================================")
    print("ERROR: COULD NOT OPEN WEBCAM")
    print("==============================================")
    print()
    print("Check your Windows camera permissions.")
    print()

    input("Press Enter to exit...")

    raise SystemExit


# ============================================================
# CAMERA RESOLUTION
# ============================================================

camera.set(
    cv2.CAP_PROP_FRAME_WIDTH,
    1280
)

camera.set(
    cv2.CAP_PROP_FRAME_HEIGHT,
    720
)


# ============================================================
# STATE VARIABLES
# ============================================================

calibrating = True

calibration_start = None

calibration_values = []

baseline_ear = None

threshold = None

eyes_closed_start = None

face_lost_start = None

drowsiness_active = False

face_lost_active = False


# ============================================================
# START MESSAGE
# ============================================================

print()
print("================================================")
print("     AI DRIVER DROWSINESS DETECTION")
print("================================================")
print()
print("Look directly at the camera.")
print()
print("Keep your eyes OPEN during calibration.")
print()
print("Calibration time:", CALIBRATION_TIME, "seconds")
print()
print("Drowsiness time:", DROWSINESS_TIME, "seconds")
print()
print("Press Q to quit.")
print()
print("================================================")
print()


# ============================================================
# MAIN LOOP
# ============================================================

while True:

    # --------------------------------------------------------
    # READ CAMERA
    # --------------------------------------------------------

    success, frame = camera.read()

    if not success:

        print(
            "ERROR: Could not read camera frame."
        )

        break


    # --------------------------------------------------------
    # Mirror camera
    # --------------------------------------------------------

    frame = cv2.flip(
        frame,
        1
    )


    # --------------------------------------------------------
    # Frame dimensions
    # --------------------------------------------------------

    height, width = frame.shape[:2]


    # --------------------------------------------------------
    # Convert BGR to RGB
    # --------------------------------------------------------

    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )


    # --------------------------------------------------------
    # Create MediaPipe image
    # --------------------------------------------------------

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )


    # --------------------------------------------------------
    # Detect face
    # --------------------------------------------------------

    result = detector.detect(
        mp_image
    )


    # ========================================================
    # FACE DETECTED
    # ========================================================

    if result.face_landmarks:

        # Face has returned
        face_lost_start = None

        face_lost_active = False


        # ----------------------------------------------------
        # Get first face
        # ----------------------------------------------------

        landmarks = (
            result.face_landmarks[0]
        )


        # ----------------------------------------------------
        # Calculate EAR
        # ----------------------------------------------------

        (
            right_ear,
            left_ear,
            average_ear
        ) = calculate_average_ear(
            landmarks,
            width,
            height
        )


        # ----------------------------------------------------
        # Draw eye landmarks
        # ----------------------------------------------------

        draw_eye_points(
            frame,
            landmarks,
            RIGHT_EYE,
            width,
            height
        )

        draw_eye_points(
            frame,
            landmarks,
            LEFT_EYE,
            width,
            height
        )


        # ====================================================
        # CALIBRATION
        # ====================================================

        if calibrating:

            # Start calibration timer
            if calibration_start is None:

                calibration_start = (
                    time.time()
                )

                print(
                    "Calibration started..."
                )


            # Save current EAR
            calibration_values.append(
                average_ear
            )


            # Calculate elapsed time
            elapsed = (
                time.time()
                -
                calibration_start
            )


            remaining = max(
                0,
                CALIBRATION_TIME -
                elapsed
            )


            # ------------------------------------------------
            # CALIBRATION DISPLAY
            # ------------------------------------------------

            cv2.putText(
                frame,
                "CALIBRATION",
                (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 255),
                3
            )


            cv2.putText(
                frame,
                "KEEP YOUR EYES OPEN",
                (30, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2
            )


            cv2.putText(
                frame,
                f"Remaining: {remaining:.1f}s",
                (30, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2
            )


            cv2.putText(
                frame,
                f"EAR: {average_ear:.3f}",
                (30, 160),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )


            # ------------------------------------------------
            # FINISH CALIBRATION
            # ------------------------------------------------

            if (
                elapsed >= CALIBRATION_TIME
                and
                len(calibration_values) > 0
            ):

                # Calculate normal EAR
                baseline_ear = (
                    sum(calibration_values)
                    /
                    len(calibration_values)
                )


                # Calculate threshold
                threshold = (
                    baseline_ear *
                    THRESHOLD_FACTOR
                )


                calibrating = False


                print()
                print(
                    "================================"
                )

                print(
                    "CALIBRATION COMPLETE"
                )

                print(
                    f"Normal EAR: "
                    f"{baseline_ear:.3f}"
                )

                print(
                    f"Drowsiness threshold: "
                    f"{threshold:.3f}"
                )

                print(
                    "================================"
                )

                print()


        # ====================================================
        # DROWSINESS DETECTION
        # ====================================================

        else:

            # ------------------------------------------------
            # Display EAR
            # ------------------------------------------------

            cv2.putText(
                frame,
                f"EAR: {average_ear:.3f}",
                (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )


            cv2.putText(
                frame,
                f"Threshold: {threshold:.3f}",
                (30, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )


            # =================================================
            # EYES CLOSED
            # =================================================

            if average_ear < threshold:

                # Start eye-closure timer
                if eyes_closed_start is None:

                    eyes_closed_start = (
                        time.time()
                    )


                # Calculate how long eyes
                # have remained closed
                closed_duration = (
                    time.time()
                    -
                    eyes_closed_start
                )


                cv2.putText(
                    frame,
                    f"Eyes closed: "
                    f"{closed_duration:.1f}s",
                    (30, 115),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 165, 255),
                    2
                )


                # =================================================
                # DROWSINESS DETECTED
                # =================================================

                if (
                    closed_duration >=
                    DROWSINESS_TIME
                ):

                    drowsiness_active = True


                    # --------------------------------------------
                    # Red screen overlay
                    # --------------------------------------------

                    overlay = frame.copy()


                    cv2.rectangle(
                        overlay,
                        (0, 0),
                        (width, height),
                        (0, 0, 255),
                        -1
                    )


                    frame = cv2.addWeighted(
                        overlay,
                        0.15,
                        frame,
                        0.85,
                        0
                    )


                    # --------------------------------------------
                    # Warning text
                    # --------------------------------------------

                    cv2.putText(
                        frame,
                        "DROWSINESS DETECTED!",
                        (30, 180),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.1,
                        (0, 0, 255),
                        4
                    )


                    cv2.putText(
                        frame,
                        "WAKE UP!",
                        (30, 230),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.3,
                        (0, 0, 255),
                        4
                    )


                    # --------------------------------------------
                    # START ALARM
                    # --------------------------------------------

                    alarm_start()


                else:

                    drowsiness_active = False

                    alarm_stop()


            # =================================================
            # EYES OPEN
            # =================================================

            else:

                # Reset eye timer
                eyes_closed_start = None

                drowsiness_active = False

                # Stop alarm
                alarm_stop()


                cv2.putText(
                    frame,
                    "STATUS: ALERT",
                    (30, 115),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )


    # ========================================================
    # NO FACE DETECTED
    # ========================================================

    else:

        # Reset eye timer
        eyes_closed_start = None


        # ====================================================
        # DURING CALIBRATION
        # ====================================================

        if calibrating:

            cv2.putText(
                frame,
                "CALIBRATION",
                (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 255),
                3
            )


            cv2.putText(
                frame,
                "SHOW YOUR FACE",
                (30, 85),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2
            )


            alarm_stop()


        # ====================================================
        # AFTER CALIBRATION
        # ====================================================

        else:

            # Start face-loss timer
            if face_lost_start is None:

                face_lost_start = (
                    time.time()
                )


            # Calculate face-loss duration
            face_lost_duration = (
                time.time()
                -
                face_lost_start
            )


            cv2.putText(
                frame,
                "NO FACE DETECTED",
                (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 165, 255),
                3
            )


            cv2.putText(
                frame,
                f"Time: "
                f"{face_lost_duration:.1f}s",
                (30, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 165, 255),
                2
            )


            # =================================================
            # FACE LOST TOO LONG
            # =================================================

            if (
                face_lost_duration >=
                NO_FACE_TIME
            ):

                face_lost_active = True


                cv2.putText(
                    frame,
                    "FACE LOST!",
                    (30, 140),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.4,
                    (0, 0, 255),
                    4
                )


                cv2.putText(
                    frame,
                    "CHECK DRIVER!",
                    (30, 190),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 255),
                    3
                )


                # Start alarm
                alarm_start()


            else:

                face_lost_active = False

                alarm_stop()


    # ========================================================
    # STATUS DISPLAY
    # ========================================================

    if not calibrating:

        if drowsiness_active:

            status = "DROWSY"

            status_color = (
                0,
                0,
                255
            )

        elif face_lost_active:

            status = "FACE LOST"

            status_color = (
                0,
                0,
                255
            )

        else:

            status = "ALERT"

            status_color = (
                0,
                255,
                0
            )


        cv2.putText(
            frame,
            f"STATUS: {status}",
            (
                width - 300,
                40
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            status_color,
            2
        )


    # ========================================================
    # SHOW CAMERA
    # ========================================================

    cv2.imshow(
        "AI Driver Drowsiness Detection",
        frame
    )


    # ========================================================
    # KEYBOARD INPUT
    # ========================================================

    key = (
        cv2.waitKey(1)
        & 0xFF
    )


    # Press Q to quit
    if key == ord("q"):

        break


# ============================================================
# CLEANUP
# ============================================================

print()
print("Stopping system...")

# Stop alarm
alarm_stop()

# Release camera
camera.release()

# Close OpenCV windows
cv2.destroyAllWindows()

# Close MediaPipe
try:

    detector.close()

except Exception:

    pass


print("System stopped.")
print("Goodbye!")