import sys
import os
import cv2
import time

max_index = 10
success_list = []
for index in range(max_index):
    cam = cv2.VideoCapture(index)
    if not cam.isOpened():
        #print(f">> error: open usb_cam = {index} failed.")
        pass
    else:
        #print(f">> info: open usb_cam = {index} success.")
        success_list.append(index)
    cam.release()   
    
for index in range(max_index):
    if index in success_list:
        print(f">> info: open usb_cam = {index} success.")
    else:
        print(f">> error: open usb_cam = {index} failed.")
