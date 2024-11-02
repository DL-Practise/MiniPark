import sys
import os
import cv2
import threading
import time
try:
    import queue
except ImportError:
    import Queue as queue
        
class UsbStream():
    def __init__(self):
        super().__init__()
        self.usb_index = 0
        self.cam_handle = None
        
        self.crop = None
        self.skip_time = None
        self.frame_queue = None
        self.thread_flag = True
        
    def start_stream(self, usb_index=0, cam_resolution=None, cam_fps=None, frame_queue=None, crop=None, rotate=None,skip_fps=None):
        if self.cam_handle is not None:
            print(f">>UsbStream:start_stream:info: the usb_cam_{self.usb_index} is already created. ignore create again")
            return True
            
        self.usb_index = usb_index
        self.cam_resolution = cam_resolution
        self.cam_fps = cam_fps
        self.frame_queue = frame_queue
        self.rotate = rotate
        if self.rotate is not None:
            assert(self.rotate in [90, 180, 270])
        self.crop = crop
        self.skip_time = 0.0 if skip_fps is None else 1.0 / skip_fps
        
        # create camera
        self.cam_handle = cv2.VideoCapture(self.usb_index)
        if not self.cam_handle.isOpened():
            print(f">>UsbStream:start_stream:error: open usb_cam_{self.usb_index} failed.")
            self.cam_handle = None
            return False
        print(f">>UsbStream:start_stream:info: open usb_cam_{self.usb_index} success")
        
        # get camera default resolution and fps
        default_resolution_w = int(self.cam_handle.get(cv2.CAP_PROP_FRAME_WIDTH))
        default_resolution_h = int(self.cam_handle.get(cv2.CAP_PROP_FRAME_HEIGHT))
        default_fps = self.cam_handle.get(cv2.CAP_PROP_FPS)
        print(f">>UsbStream:create_stream:info: the usb_cam_{self.usb_index} default resolution is [{default_resolution_w}*{default_resolution_h}] default fps is {default_fps}")
      
        # set camera resolution and fps
        if cam_resolution is not None or cam_fps is not None:
            pass
            new_resolution_w = int(self.cam_handle.get(cv2.CAP_PROP_FRAME_WIDTH))
            new_resolution_h = int(self.cam_handle.get(cv2.CAP_PROP_FRAME_HEIGHT))
            new_fps = self.cam_handle.get(cv2.CAP_PROP_FPS)
            print(f">>UsbStream:create_stream:info: the usb_cam_{self.usb_index} new resolution is [{new_resolution_w}*{new_resolution_h}] new fps is {new_fps}")
          
        # start stream thread
        self.thread_flag = True
        t = threading.Thread(target=self.stream_thread, args=(), daemon=True)
        t.start()
        
    def stop_stream(self):
        if self.cam_handle is None:
            print(f">>UsbStream:stop_stream:info: the usb_cam_{self.usb_index} is not started, ignore stop.")
            return True
            
        # stop the thread if need
        self.thread_flag = False
        time.sleep(0.1)
        print(f">>UsbStream:stop_stream:info: stop the stream thread by set the thread flag to False")
        
        # release camera
        self.cam_handle.release()
        print(f">>UsbStream:stop_stream:info: release the camera")
        
    def stream_thread(self):
        pid = threading.current_thread().ident
        print(f">>UsbStream:stream_thread:info: the stream thread({pid}) is starting.")
        
        frame_time = time.time()
        while self.thread_flag:
            #print(f">>UsbStream:stream_thread({pid}):info: 111111111")
            ret, frame = self.cam_handle.read()
            #print(f">>UsbStream:stream_thread({pid}):info: 222222222")
            if not ret:
                print(f">>UsbStream:stream_thread:error: read one frame failed.")
                break
                
            print(f">>UsbStream:stream_thread({pid}):info: get one frame from camera")
            cur_time = time.time()
            time_intval = cur_time - frame_time
            if time_intval < self.skip_time:
                time.sleep(self.skip_time - time_intval)
                continue
                
            frame_time = cur_time
            if self.crop is not None:
                h, w, c = frame.shape
                x0,y0,x1,y1 = self.crop
                x0 = max(0, x0)
                y0 = max(0, y0)
                x1 = min(w, x1)
                y1 = min(h, y1)
                frame = frame[y0:y1+1,x0:x1+1,:]
                
            if self.rotate is not None:
                if self.rotate == 90:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                if self.rotate == 180:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                if self.rotate == 270:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            if self.frame_queue is not None:
                if self.frame_queue.full():
                    #print(f">>UsbStream:stream_thread:warn: the queue is full, skip put")
                    time.sleep(0.01)
                    continue
                else:
                    self.frame_queue.put(frame)
                    #print(f">>UsbStream:stream_thread:info: put one frame to queue")
        
        print(f">>UsbStream:stream_thread:info: the stream thread is stopping.")
        self.stop_stream()

class UsbCombineStream():
    def __init__(self, index_list=[0,1], 
                       frame_queue = None,
                       crop_list=[None, None],
                       rotate_list=[None, None]):
        super().__init__()

        self.index_list = index_list
        self.frame_queue = frame_queue
        self.crop_list = crop_list
        self.rotate_list = rotate_list  

        self.camera = None
        self.thread_flag = True
        
        #self.camera_list = [None, None]

        if self.rotate_list[0] is not None:
            assert(self.rotate_list[0] in [90, 180, 270])
        if self.rotate_list[1] is not None:
            assert(self.rotate_list[1] in [90, 180, 270])
        
    def start_stream(self):
        # create camera
        self.camera = cv2.VideoCapture(self.index_list[0])
        if not self.camera.isOpened():
            raise Exception(f">>UsbCombineStream:start_stream:error: open usb_cam_{self.index_list[0]} failed.")
        self.camera.release()
        self.camera = None
        
        self.camera = cv2.VideoCapture(self.index_list[1])
        if not self.camera.isOpened():
            raise Exception(f">>UsbCombineStream:start_stream:error: open usb_cam_{self.index_list[1]} failed.")
        self.camera.release()
        self.camera = None
            
        # start stream thread
        self.thread_flag = True
        t = threading.Thread(target=self.stream_thread, args=(), daemon=True)
        t.start()
        
    def stop_stream(self):
        # stop the thread if need
        self.thread_flag = False
        time.sleep(0.5)
        
        # release camera
        if self.camera is not None:
            self.camera.release()
            self.camera = None
            
        

        print(f">>UsbCombineStream:stop_stream:info: finished stop the camera")
        
    def stream_thread(self):
        print(f">>UsbCombineStream:stream_thread:info: the stream thread is starting.")
        
        #self.camera_list[0] = cv2.VideoCapture(self.index_list[0])
        #self.camera_list[1] = cv2.VideoCapture(self.index_list[1])
        
        frame_time = time.time()
        while self.thread_flag:
            self.camera = cv2.VideoCapture(self.index_list[0])
            ret0, frame0 = self.camera.read()
            self.camera.release()
            self.camera = None 
            
            self.camera = cv2.VideoCapture(self.index_list[1])
            ret1, frame1 = self.camera.read()
            self.camera.release()
            self.camera = None 

            if not ret0 or not ret1:
                raise Exception(f">>UsbCombineStream:stream_thread:error: read one frame failed.")
            
            if self.crop_list[0] is not None:
                h, w, c = frame0.shape
                x0,y0,x1,y1 = self.crop_list[0]
                x0 = max(0, x0)
                y0 = max(0, y0)
                x1 = min(w, x1)
                y1 = min(h, y1)
                frame0 = frame0[y0:y1+1,x0:x1+1,:]
                
            if self.crop_list[1] is not None:
                h, w, c = frame1.shape
                x0,y0,x1,y1 = self.crop_list[1]
                x0 = max(0, x0)
                y0 = max(0, y0)
                x1 = min(w, x1)
                y1 = min(h, y1)
                frame1 = frame1[y0:y1+1,x0:x1+1,:]
                
            if self.rotate_list[0] is not None:
                if self.rotate_list[0] == 90:
                    frame0 = cv2.rotate(frame0, cv2.ROTATE_90_CLOCKWISE)
                if self.rotate_list[0] == 180:
                    frame0 = cv2.rotate(frame0, cv2.ROTATE_180)
                if self.rotate_list[0] == 270:
                    frame0 = cv2.rotate(frame0, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    
            if self.rotate_list[1] is not None:
                if self.rotate_list[1] == 90:
                    frame1 = cv2.rotate(frame1, cv2.ROTATE_90_CLOCKWISE)
                if self.rotate_list[1] == 180:
                    frame1 = cv2.rotate(frame1, cv2.ROTATE_180)
                if self.rotate_list[1] == 270:
                    frame1 = cv2.rotate(frame1, cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            cur_time = time.time()
            #print(f"*** cur_time is {cur_time}")
            if self.frame_queue is not None:
                if self.frame_queue.full():
                    #time.sleep(0.1)
                    continue
                else:
                    self.frame_queue.put([frame0, frame1])
        
        print(f">>UsbStream:stream_thread:info: the stream thread is stopping.")
          
if __name__ == "__main__":
    stream = UsbCombineStream(index_list=[0,2], rotate_list=[90, 90])
    stream.start_stream()
    time.sleep(10)
    stream.stop_stream()