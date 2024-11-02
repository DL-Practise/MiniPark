# coding:utf-8
try:
    import RPi.GPIO as GPIO
except RuntimeError:
    print("Error importing RPi.GPIO!  This is probably because you need superuser privileges. "
          " You can achieve this by using 'sudo' to run your script")
import time

def angle_to_duty(angle_value):
    angle_min, angle_max = 0.0, 180.0
    duty_min, duty_max = 2.5, 12.5
    percent = (angle_value - angle_min) / (angle_max - angle_min)
    duty_value = duty_min + percent * (duty_max - duty_min)
    return duty_value

def steering_engine_start(io_num=40, start_angle=0):
    pwm_handle = GPIO.PWM(io_num, 50)
    duty = angle_to_duty(start_angle)
    pwm_handle.start(duty)
    return pwm_handle

#last_angle = None
def steering_engine_control(pwm_handle, angle):
    #global last_angle
    #if last_angle is None:
        duty = angle_to_duty(angle)
        pwm_handle.ChangeDutyCycle(duty)
    #else:
    #    for i in list(range(last_angle, angle, 1 if angle >= last_angle else -1)):
    #        duty = angle_to_duty(i)
    #        pwm_handle.ChangeDutyCycle(duty)
    #        time.sleep(0.1)
    #last_angle = angle


def steering_engine_stop(pwm_handle):
    pwm_handle.stop()
    
if __name__ == "__main__":
    seering_engine_io = 40
    GPIO.setmode(GPIO.BOARD) 
    GPIO.setup(seering_engine_io, GPIO.OUT)
    
    pwm_handle = steering_engine_start(seering_engine_io)
    while True:
        input_str = input("input 0-180 to control. any char to exit")
        try:
            angle = int(input_str)
            print(f"get input angle={angle}")
            steering_engine_control(pwm_handle, angle)
        except Exception as e:
            print(f"exit: {str(e)}")
            steering_engine_stop(pwm_handle)
            break
    
    GPIO.cleanup() 

