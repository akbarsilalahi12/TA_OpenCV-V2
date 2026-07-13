import cv2
import numpy as np
import pickle
import time
import os
import threading

# =========================
# RTSP CCTV
# =========================
RTSP_URL = "rtsp://admin:L2E1141F@10.134.84.205:554/cam/realmonitor?channel=1&subtype=0"

# =========================
# RTSP READER (auto-reconnect)
# =========================
class RTSPReader:
    def __init__(self, url, target_size=(1280,720), reconnect_delay=3):
        self.url = url
        self.target_size = target_size
        self.reconnect_delay = reconnect_delay
        self._cap = None
        self._frame = None
        self._frame_lock = threading.Lock()
        self._stop = threading.Event()
        self._connected = False

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self._stop.set()
        if self._cap:
            self._cap.release()

    def is_connected(self):
        return self._connected

    def get_latest_frame(self):
        with self._frame_lock:
            return self._frame.copy() if self._frame is not None else None

    def _open(self):
        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except:
            pass
        if not cap.isOpened():
            cap.release()
            return None
        return cap

    def _run(self):
        while not self._stop.is_set():
            if self._cap is None or not self._cap.isOpened():
                print("RTSP connecting...")
                self._cap = self._open()
                if self._cap is None:
                    self._connected = False
                    time.sleep(self.reconnect_delay)
                    continue
                self._connected = True
                print("RTSP connected")

            self._cap.grab()
            ret, frame = self._cap.read()
            if not ret or frame is None:
                print("Frame lost, reconnecting...")
                self._cap.release()
                self._cap = None
                self._connected = False
                time.sleep(self.reconnect_delay)
                continue

            if self.target_size:
                frame = cv2.resize(frame, self.target_size)

            with self._frame_lock:
                self._frame = frame

# =========================
# INIT RTSP
# =========================
reader = RTSPReader(RTSP_URL)
reader.start()
time.sleep(2)

# =========================
# LOAD POLYGON SLOT
# =========================
posList = []

if os.path.exists("carParkPos"):

    with open("carParkPos", "rb") as f:

        posList = pickle.load(f)

# =========================
# SHADOW MASK (HSV)
# =========================
def createShadowMask(frameBgr):
    hsv = cv2.cvtColor(frameBgr, cv2.COLOR_BGR2HSV)
    _, v, _ = cv2.split(hsv)
    shadow = cv2.inRange(v, 20, 80)
    kernel = np.ones((5,5), np.uint8)
    shadow = cv2.morphologyEx(shadow, cv2.MORPH_CLOSE, kernel)
    shadow = cv2.morphologyEx(shadow, cv2.MORPH_OPEN, kernel)
    return shadow

# =========================
# ADAPTIVE THRESHOLD
# =========================
def computeThreshold(frameGray, baseTh=0.18):
    meanBrightness = float(np.mean(frameGray))
    factor = meanBrightness / 128.0
    adjusted = baseTh * factor
    return max(0.08, min(0.35, adjusted))

# =========================
# CHECK PARKING
# =========================
def checkParkingSpace(frame, processed, frameGray, shadowMask):

    spaceCount = 0
    baseTh = 0.18
    actualTh = computeThreshold(frameGray, baseTh)

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

        # =========================
        # SHADOW ADJUSTMENT
        # =========================
        effectiveArea = area
        if shadowMask is not None:
            shadowRoi = shadowMask[y:y+h, x:x+w]
            if shadowRoi.shape[:2] == mask.shape[:2]:
                shadowInPoly = cv2.bitwise_and(shadowRoi, shadowRoi, mask=mask)
                shadowPixels = cv2.countNonZero(shadowInPoly)
                effectiveArea = max(1.0, area - shadowPixels)

        ratio = count / area
        effectiveRatio = count / effectiveArea

        # =========================
        # DETECTION
        # =========================
        if effectiveRatio < actualTh:

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
    frame = reader.get_latest_frame()
    if frame is None:
        if not reader.is_connected():
            print("Waiting for RTSP connection...")
        time.sleep(0.1)
        continue

    # =========================
    # PREPROCESS
    # =========================
    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    # =========================
    # CLAHE (tahan cahaya)
    # =========================
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    grayEq = clahe.apply(gray)

    blur = cv2.GaussianBlur(
        grayEq,
        (5,5),
        1
    )

    # =========================
    # ADAPTIVE THRESHOLD
    # =========================
    thresh = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        5
    )

    # =========================
    # SHADOW REMOVAL
    # =========================
    shadowMask = createShadowMask(frame)
    thresh = cv2.bitwise_and(thresh, cv2.bitwise_not(shadowMask))

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
    # MORPHOLOGICAL CLOSE
    # =========================
    closeKernel = np.ones((3,3), np.uint8)
    dilate = cv2.morphologyEx(dilate, cv2.MORPH_CLOSE, closeKernel)

    # =========================
    # CHECK SLOT
    # =========================
    checkParkingSpace(
        frame,
        dilate,
        gray,
        shadowMask
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
reader.stop()
cv2.destroyAllWindows()