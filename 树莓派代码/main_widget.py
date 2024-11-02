# -*- coding: utf-8 -*-
import sys
sys.path.append("/usr/lib/python3/dist-packages")
import os
import PyQt5
from PyQt5.QtWidgets import *
from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import copy
import numpy as np
import logging
import threading
from threading import Timer
import subprocess
import time
import cv2
from stream import UsbCombineStream
try:
    import queue
except ImportError:
    import Queue as queue
import traceback
from alg_module.zx_onnx_infer import license_plate_det

import platform
os_name = platform.system()
if os_name != "Windows":
    from steering_module.test_pigpio import steering_engine_init, steering_engine_control

# ui配置文件
cUi, cBase = uic.loadUiType("main_widget.ui")
 
# 主界面
class CMainWidget(QWidget, cUi):
    def __init__(self):
        # 设置UI
        QMainWindow.__init__(self)
        cUi.__init__(self)
        self.setupUi(self)
        
        # config info 
        self.time_in_delay = 5
        self.time_out_delay = [5,5]
        self.price = 5.0
        self.back_color = "#003f98"
        self.back_img = "./source/back.png"
        self.record_img = cv2.imread("./source/record.png")
        self.record_img = cv2.cvtColor(self.record_img, cv2.COLOR_BGR2RGB)
        if os_name != "Windows":
            self.stream_urls = [2, 0]
        else:
            self.stream_urls = [0, 1]
        
        self.setStyleSheet(f"QWidget {{ background-color: {self.back_color}; }}")
        self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint)
        self.show_back_cvrgb = cv2.cvtColor(cv2.imread(self.back_img), cv2.COLOR_BGR2RGB)
        self.show_frame_in = None
        self.show_frame_out = None
        self.show_cmd = "no cmd"
        self.show_in_license = None
        self.show_out_license = None
        self.show_out_time = None
        self.show_out_money = None
        self.debug = False
        
        self.last_state_name = ""
        self.state_name = "detect_nothing" #detect_nothing/detect_in/detect_out
        self.state_time = 0
        
        self.frame_queue = queue.Queue(maxsize=1)
        if not self.debug:
            self.stream = UsbCombineStream(index_list=self.stream_urls, frame_queue=self.frame_queue, rotate_list=[90, 90])
        else:
            self.stream = None
        if os_name != "Windows":
            self.duoji_io = 21
            self.duoji_handle = steering_engine_init(self.duoji_io, 30)
        
        self.car_time = {}
        
        
        self.alg_thread_flag = True
        threading.Thread(target=self.alg_thread, args=(), daemon=True).start()
        
        if not self.debug:
            self.stream.start_stream()

        self.showMaximized()

    def alg_thread(self):
        print('>>CMainWidget:alg_thread: the thread is starting')
        while self.alg_thread_flag:
            # if debug not use alg
            if self.debug:
                time.sleep(0.2)
                continue
                
            try:
                frame_in, frame_out = self.frame_queue.get(block=True, timeout=0.5)
                #print('>>CMainWidget:alg_thread:info: get one frame of camera in')
                self.show_frame_in = copy.deepcopy(frame_in)
                self.show_frame_out = copy.deepcopy(frame_out)
                self.show_frame_in = cv2.cvtColor(self.show_frame_in, cv2.COLOR_BGR2RGB)
                self.show_frame_out = cv2.cvtColor(self.show_frame_out, cv2.COLOR_BGR2RGB)
            except queue.Empty:
                frame_in = None
                frame_out = None
                #print('>>CMainWidget:alg_thread:warn: get no frame of camera in')
                continue
            
            if self.state_name == "detect_nothing":
                in_h, in_w, in_c = frame_in.shape
                out_h, out_w, out_c = frame_out.shape
                print(f">>CMainWidget:alg_thread: frame_in shape={in_h}*{in_w}*{in_c} frame_out shape={out_h}*{out_w}*{out_c}")
                assert(in_h == out_h)
                assert(in_w == out_w)
                
                frame_cat = np.hstack((frame_in, frame_out))
                frame_cat = cv2.resize(frame_cat, (640, 640))
                print(f">>CMainWidget:alg_thread: frame_cat shape={frame_cat.shape}")
                
                result_list = license_plate_det(frame_cat)
                if len(result_list) > 0:
                    # only use the first
                    result = result_list[0]
                    print(f">>CMainWidget:alg_thread: det license={result['plate_no']} in_out={result['in_out']} score={result['score']:.2f} char_score={result['char_score_mean']:.2f};{result['char_score_min']:.2f}")
                    if result['char_score_min'] > 0.9:
                        print(f">>CMainWidget:alg_thread: this is a valid result")
                        if result['in_out'] == "in":
                            self.show_cmd = f"get license from in camera({result['plate_no']})"
                            self.show_in_license = result['plate_no']
                            self.car_time[result['plate_no']] = time.time()
                            self.state_name = "detect_in"
                            threading.Thread(target=self.time_thread, args=(), daemon=True).start()
                        elif result['in_out'] == "out":
                            self.show_cmd = f"get license form out camera({result['plate_no']})"
                            self.show_out_license = result['plate_no']
                            out_time = time.time()
                            if result['plate_no'] in self.car_time:
                                in_time = self.car_time[result['plate_no']]
                            else:
                                in_time = out_time
                            hour, min, sec, cost = self.calculate_time_cost(in_time, out_time)
                            self.show_out_time = f"{hour}小时{min}分{sec}秒"
                            self.show_out_money = f"收费:{cost:.3f}元"
                            self.state_name = "detect_out"
                            threading.Thread(target=self.time_thread, args=(), daemon=True).start()
            self.update()
                    
    def time_thread(self):
        print('>>CMainWidget:time_thread:info: the thread is starting')
        if self.state_name == "detect_in":
            if os_name != "Windows":
                steering_engine_control(self.duoji_handle, self.duoji_io, 120)
            time.sleep(self.time_in_delay) # wait for pass
            if os_name != "Windows":
                steering_engine_control(self.duoji_handle, self.duoji_io, 30)
        if self.state_name == "detect_out":
            time.sleep(self.time_out_delay[0]) # wait for pay
            if os_name != "Windows":
                steering_engine_control(self.duoji_handle, self.duoji_io, 120)
            time.sleep(self.time_out_delay[1]) # wait for pass
            if os_name != "Windows":
                steering_engine_control(self.duoji_handle, self.duoji_io, 30)
        self.state_name = "detect_nothing"
        self.update()
        
    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        
        painter = QPainter(self)    # 创建绘图对象
        #painter.setPen(Qt.red)     # 设置画笔
        #painter.drawEllipse(80, 10, 50, 30)   # 绘制一个椭圆
        #painter.drawRect(180, 10, 50, 30)    # 绘制一个矩形
        #painter.drawLine(80, 70, 200, 70)     # 绘制直线
        
        if self.state_name == "detect_nothing":
            if self.show_back_cvrgb is not None:
                height, width, depth = self.show_back_cvrgb.shape
                qimage = QImage(self.show_back_cvrgb, width, height, width*depth, QImage.Format_RGB888)
                qpixmap = QtGui.QPixmap(qimage)
                painter.drawPixmap(QtCore.QRect(0,0,w,h), qpixmap)
                
        if self.state_name == "detect_in":
            if self.show_frame_in is not None:
                height, width, depth = self.show_frame_in.shape
                qimage = QImage(self.show_frame_in, width, height, width*depth, QImage.Format_RGB888)
                qpixmap = QtGui.QPixmap(qimage)
                painter.drawPixmap(QtCore.QRect(int(w*0.05),int(h*0.1),int(w*0.4),int(h*0.8)), qpixmap)
            if self.show_in_license is not None:
                painter.setPen(QColor(250,250,250))
                painter.setFont(QFont('SimSun',60))
                painter.drawText(int(w*0.50), int(h*0.20), self.show_in_license)
                painter.drawText(int(w*0.50), int(h*0.40), "欢迎光临")
                
        if self.state_name == "detect_out":
            if self.show_frame_out is not None:
                height, width, depth = self.show_frame_out.shape
                qimage = QImage(self.show_frame_out, width, height, width*depth, QImage.Format_RGB888)
                qpixmap = QtGui.QPixmap(qimage)
                painter.drawPixmap(QtCore.QRect(int(w*0.05),int(h*0.1),int(w*0.4),int(h*0.8)), qpixmap)
            if self.show_out_license is not None:
                painter.setPen(QColor(250,250,250))
                painter.setFont(QFont('SimSun',60))
                painter.drawText(int(w*0.48), int(h*0.20), self.show_out_license)
                painter.drawText(int(w*0.48), int(h*0.35), self.show_out_time)
                painter.drawText(int(w*0.48), int(h*0.50), self.show_out_money)
                
            if self.record_img is not None:
                height, width, depth = self.record_img.shape
                qimage = QImage(self.record_img, width, height, width*depth, QImage.Format_RGB888)
                qpixmap = QtGui.QPixmap(qimage)
                painter.drawPixmap(QtCore.QRect(int(w*0.55),int(h*0.55),int(w*0.22),int(w*0.22)), qpixmap)
                        
        # draw cmd
        painter.setPen(QColor(100,0,0))
        painter.setFont(QFont('SimSun',10))
        painter.drawText(int(w*0.01), int(h*0.99), self.show_cmd)

    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            print(f"CMainWidget:keyPressEvent:info get key Esc, exit")
            self.show_cmd = "get key Esc, exit"
            self.close()
        else: 
            print(f"CMainWidget:keyPressEvent:info get key {event.key()}, ignore")
            self.show_cmd = f"get key {event.key()}, ignore"
            
        self.update()

    def closeEvent(self, event):
        if not self.debug:
            self.stream.stop_stream()
        self.alg_thread_flag = False
        time.sleep(0.1)
        event.accept()

    def calculate_time_cost(self, in_time, out_time):
        in_min, in_sec = divmod(in_time, 60)
        in_hour, in_min = divmod(in_min, 60)
        out_min, out_sec = divmod(out_time, 60)
        out_hour, out_min = divmod(out_min, 60)

        cost = (out_time - in_time) * (self.price / 3600.)
        return int(out_hour-in_hour), int(out_min-in_min), int(out_sec-in_sec), cost

if __name__ == '__main__':
    
    cApp = QApplication(sys.argv)
    main_widget = CMainWidget()
    main_widget.show()
    sys.exit(cApp.exec_())