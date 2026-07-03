import cv2
import numpy as np
import pickle
import time
import os

# =========================
# RTSP CCTV
# =========================
RTSP_URL = "rtsp://admin:L2E1141F@10.173.18.205:554/cam/realmonitor?channel=1&subtype=0"

# =========================
# OPEN RTSP
# =========================
def open_capture(source):

    cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        return None

    return cap

cap = open_capture(RTSP_URL)

# =========================
# LOAD POLYGON SLOT
# =========================
posList = []

if os.path.exists("carParkPos"):

    with open("carParkPos", "rb") as f:

        posList = pickle.load(f)

# =========================
# CHECK PARKING
# =========================
def checkParkingSpace(frame, processed):

    spaceCount = 0

    for poly in posList:

        pts = np.array(poly, np.int32)

        # =========================
        # BOUNDING RECT
        # =========================
        x, y, w, h = cv2.boundingRect(pts)

        # crop ROI
        roi = processed[y:y+h, x:x+w]

        # =========================
        # LOCAL POLYGON
        # =========================
        local_pts = pts - [x, y]

        # create mask
        mask = np.zeros((h, w), dtype=np.uint8)

        cv2.fillPoly(mask, [local_pts], 255)

        # apply polygon mask
        masked = cv2.bitwise_and(
            roi,
            roi,
            mask=mask
        )

        # =========================
        # PIXEL COUNT
        # =========================
        count = cv2.countNonZero(masked)

        area = cv2.contourArea(local_pts)

        # avoid divide by zero
        if area == 0:
            continue

        ratio = count / area

        # =========================
        # DETECTION
        # =========================
        # TUNE THIS VALUE
        if ratio < 0.18:

            color = (0,255,0)
            status = "FREE"

            spaceCount += 1

        else:

            color = (0,0,255)
            status = "FULL"

        # =========================
        # DRAW POLYGON
        # =========================
        cv2.polylines(
            frame,
            [pts],
            True,
            color,
            2
        )

        # =========================
        # CENTER TEXT
        # =========================
        M = cv2.moments(pts)

        if M["m00"] != 0:

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            cv2.putText(
                frame,
                status,
                (cx - 25, cy),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2
            )

            cv2.putText(
                frame,
                f"{ratio:.2f}",
                (cx - 20, cy + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255,255,255),
                1
            )

    # =========================
    # COUNTER UI
    # =========================
    cv2.rectangle(
        frame,
        (40,20),
        (340,90),
        (180,0,180),
        -1
    )

    cv2.putText(
        frame,
        f"Free: {spaceCount}/{len(posList)}",
        (55,65),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255,255,255),
        2
    )

# =========================
# MAIN LOOP
# =========================
while True:

    # reconnect RTSP
    if cap is None or not cap.isOpened():

        print("Reconnecting RTSP...")

        time.sleep(2)

        cap = open_capture(RTSP_URL)

        continue

    # skip old frame
    cap.grab()

    ret, frame = cap.read()

    if not ret:

        print("Frame lost!")

        cap.release()

        cap = None

        continue

    # =========================
    # RESIZE
    # =========================
    frame = cv2.resize(frame, (1280,720))

    # =========================
    # PREPROCESS
    # =========================
    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    blur = cv2.GaussianBlur(
        gray,
        (5,5),
        1
    )

    # =========================
    # BETTER THAN ADAPTIVE
    # =========================
    _, thresh = cv2.threshold(
        blur,
        150,
        255,
        cv2.THRESH_BINARY_INV
    )

    median = cv2.medianBlur(
        thresh,
        5
    )

    kernel = np.ones((3,3), np.uint8)

    dilate = cv2.dilate(
        median,
        kernel,
        iterations=1
    )

    # =========================
    # CHECK SLOT
    # =========================
    checkParkingSpace(
        frame,
        dilate
    )

    # =========================
    # SHOW WINDOWS
    # =========================
    cv2.imshow(
        "Parking Detection",
        frame
    )

    cv2.imshow(
        "Processed",
        dilate
    )

    # =========================
    # EXIT
    # =========================
    key = cv2.waitKey(1) & 0xFF

    if key == 27 or key == ord('q'):

        break

# =========================
# CLEANUP
# =========================
if cap:

    cap.release()

cv2.destroyAllWindows()