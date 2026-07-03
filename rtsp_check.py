import cv2
import sys
url = sys.argv[1] if len(sys.argv)>1 else ''
cap = cv2.VideoCapture(url)
print('isOpened', cap.isOpened())
cap.release()
