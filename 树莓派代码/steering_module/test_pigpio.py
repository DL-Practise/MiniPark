import pigpio
import time


def angle_to_duty(angle_value):
    angle_min, angle_max = 0.0, 180.0
    duty_min, duty_max = 500.0, 2500.0
    percent = (angle_value - angle_min) / (angle_max - angle_min)
    duty_value = int(duty_min + percent * (duty_max - duty_min))
    return duty_value

last_angle = None
def steering_engine_init(io_num=21, start_angle=0):
    global last_angle
    pi = pigpio.pi()
    pi.set_PWM_range(pin, 20000)
    pi.set_PWM_frequency(pin, 50) 
    duty = angle_to_duty(start_angle)
    pi.set_PWM_dutycycle(io_num, duty)
    #last_angle = start_angle
    return pi

def steering_engine_control(pi, io_num=21, angle=0):
    global last_angle
    if last_angle is None:
        duty = angle_to_duty(angle)
        pi.set_PWM_dutycycle(io_num, duty)
    else:
        for i in list(range(last_angle, angle, 1 if angle >= last_angle else -1)):
            duty = angle_to_duty(i)
            pi.set_PWM_dutycycle(io_num, duty)
            time.sleep(0.1)
    #last_angle = angle
    

pin = 21 #18

if __name__ == "__main__":
    io_num = 21
    pwm_handle = steering_engine_init(io_num,30)
    while True:
        input_str = input("input 0-180 to control. any char to exit")
        try:
            angle = int(input_str)
            print(f"get input angle={angle}")
            steering_engine_control(pwm_handle, io_num, angle)
        except Exception as e:
            print(f"exit: {str(e)}")
            break
            
            
            
            
