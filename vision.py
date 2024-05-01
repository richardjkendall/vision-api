import logging
import uuid
import os
import time

import cv2
import numpy as np
from urllib.request import urlopen

logger = logging.getLogger(__name__)

def url_to_image(url, readFlag=cv2.IMREAD_COLOR):
  resp = urlopen(url)
  image = np.asarray(bytearray(resp.read()), dtype="uint8")
  image = cv2.imdecode(image, readFlag)
  return image

def determine_day_or_night(img):
  avg_col = img.mean(axis=0).mean(axis=0)
  day = True
  if avg_col[0] == avg_col.mean():
    day = False
  return day

def extract_roi(img, points):
  pt_A = points[0]
  pt_B = points[1]
  pt_C = points[2]
  pt_D = points[3]

  width_AD = np.sqrt(((pt_A[0] - pt_D[0]) ** 2) + ((pt_A[1] - pt_D[1]) ** 2))
  width_BC = np.sqrt(((pt_B[0] - pt_C[0]) ** 2) + ((pt_B[1] - pt_C[1]) ** 2))
  maxWidth = max(int(width_AD), int(width_BC))
  
  height_AB = np.sqrt(((pt_A[0] - pt_B[0]) ** 2) + ((pt_A[1] - pt_B[1]) ** 2))
  height_CD = np.sqrt(((pt_C[0] - pt_D[0]) ** 2) + ((pt_C[1] - pt_D[1]) ** 2))
  maxHeight = max(int(height_AB), int(height_CD))

  input_pts = np.float32([pt_A, pt_B, pt_C, pt_D])
  output_pts = np.float32([[0, 0],
                          [0, maxHeight - 1],
                          [maxWidth - 1, maxHeight - 1],
                          [maxWidth - 1, 0]])

  M = cv2.getPerspectiveTransform(input_pts, output_pts)
  out = cv2.warpPerspective(img, M, (maxWidth, maxHeight), flags=cv2.INTER_LINEAR)
  return out

def find_dark_regions(img, upper):
  median = cv2.medianBlur(img, 5)
  lower = (0, 0, 0)
  thresh = cv2.inRange(median, lower, upper)
  return thresh

def find_gate_slats(img, height):
  vert = img.copy()
  vs = cv2.getStructuringElement(cv2.MORPH_RECT, (1, height))
  vert = cv2.erode(vert, vs)
  vert = cv2.dilate(vert, vs)
  vert = cv2.dilate(vert, vs)
  return vert

def determine_gate_geometry(img):
  contours = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
  contours = contours[0] if len(contours) == 2 else contours[1]

  h, w = img.shape
  result = np.zeros((h, w, 3), np.uint8)
  result = cv2.bitwise_not(result)

  slats = []
  gate_min_x = 1000
  gate_max_x = 0
  gate_min_y = 1000
  gate_max_y = 0

  for c in contours:
      x, y, w, h = cv2.boundingRect(c)
      if h > 150:
          cv2.line(result, (x, y), (x, y+h), (255, 0, 0), 2)
          if x < gate_min_x:
              gate_min_x = x
          if x+w > gate_max_x:
              gate_max_x = x+w
          if y < gate_min_y:
              gate_min_y = y
          if y+h > gate_max_y:
              gate_max_y = y+h
          slats.append(c)
  
  if len(slats) > 0:
    cv2.rectangle(result, (gate_min_x, gate_min_y), (gate_max_x, gate_max_y), (0, 0, 255), 2)
  else:
     gate_min_x = -1
     gate_min_y = -1

  return {
     "slats": slats,
     "rect": [
        [gate_min_x, gate_min_y],
        [gate_max_x, gate_max_y]
     ],
     "img": result
  }
  
def get_gate_status(debug = False):
  # get UUID
  id = str(uuid.uuid4())
  st = time.time()

  # get camera password from environment
  username = os.environ.get("CAM_USER")
  password = os.environ.get("CAM_PWD")
  if not password or not username:
     logger.error("No username/password found in environment")
     raise Exception("No username/password in environment")

  # get image from camera
  logger.info("Getting picture from camera...")
  src_img = url_to_image(f"http://driveway.cam.bhop.local/cgi-bin/api.cgi?cmd=Snap&channel=0&rs=123abc&user={username}&password={password}")
  logger.info("Got image from camera.")
  if debug:
    cv2.imwrite(f"debug/{id}_01_src.jpg", src_img)

  # determine if it is day or night
  day = determine_day_or_night(src_img)
  logger.info(f"Day = {day}")

  # get ROI
  roi_points = [
    [1865, 421],
    [1838, 662],
    [2295, 868],
    [2355, 600]
  ]
  roi = extract_roi(src_img, roi_points)
  if debug:
    cv2.imwrite(f"debug/{id}_02_roi.jpg", roi)

  # get dark regions
  upper = (80, 80, 80)
  if not day:
    upper = (30, 30, 30)
  thresh = find_dark_regions(roi, upper)
  if debug:
    cv2.imwrite(f"debug/{id}_03_thresh.jpg", thresh)

  # find gate slats
  vert = find_gate_slats(thresh, 250)
  if debug:
    cv2.imwrite(f"debug/{id}_04_vert.jpg", vert)

  # get geometry
  geom = determine_gate_geometry(vert)
  if debug:
    cv2.imwrite(f"debug/{id}_05_result.jpg", geom["img"])

  # prepare results and return them
  gate_left_edge = geom["rect"][0][0]
  logger.info(f"Gate left edge = {gate_left_edge}")
  percentage_gate_fill = 1 - (gate_left_edge / 513)
  if gate_left_edge == -1:
    logger.info("Setting percentage gate fill to 0 as left edge is -1")
    percentage_gate_fill = 0
  gap_size = 3.2 * (1 - percentage_gate_fill)
  et = time.time()

  return {
     "id": id,
     "slats": len(geom["slats"]),
     "percentage_gate_fill": 0 if percentage_gate_fill < 0 else percentage_gate_fill,
     "gap_size": 0 if gap_size < 0 else gap_size,
     "day": day,
     "gate_rect": geom["rect"],
     "runtime": et - st
  }