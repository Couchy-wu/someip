#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo_struct.py —— 结构化赋值 → C++ 库序列化组包 → 发送给客户端
演示：对 RTK / IMU / Broadcast / PilotStatus / VehiclePosition 等数据结构赋值，
由 C++ 库（libarhud_server.so）序列化（大端 + CRC32）并通过 vsomeip 发送。

运行：python3 demo_struct.py [本机IP]    （板端客户端订阅后即可收到）
"""
import sys
import time

sys.path.insert(0, __file__ and __import__("os").path.dirname(__file__))
from arhud_py import ArHudServer


def main():
    unicast = sys.argv[1] if len(sys.argv) > 1 else None
    srv = ArHudServer(unicast=unicast)
    srv.start()
    print("[demo] 服务端已启动（11 服务 / 23 事件，major=1）", flush=True)

    n = 0
    try:
        while True:
            n += 1
            # ---- 按功能需求对数据结构赋值 ----
            svc, ev, payload = srv.notify_fields(
                "RTK", counter=n,
                rtk_status=1, utc_time_us=1000.0 + n, sys_time_us=2000.0 + n,
                longitude=116.397, latitude=39.908, altitude=50.0,
                longitude_acc=0.01, latitude_acc=0.01, altitude_acc=0.02,
                heading_move=90.0, heading_double_ant=90.1, heading_move_acc=0.1,
                speed_2d=60.0, speed_acc=0.1, speed_n=1.0, speed_e=2.0, speed_u=0.0,
                g_dop=1.1, h_dop=0.9, v_dop=1.2,
                satellite_num=20, satellite_used=18, snr_max=45.0, snr_mix=30.0, snr_avr=38.5)
            print(f"[send] RTK(0x{svc:04X}/0x{ev:04X}) #{n} len={len(payload)}", flush=True)

            srv.notify_fields("IMU", counter=n,
                              angular_velocity_x=0.01, angular_velocity_y=0.02,
                              angular_velocity_z=0.03, acc_speed_x=0.1, acc_speed_y=0.2,
                              acc_speed_z=9.8, IMU_status=1, IMU_current_temperature=35.5,
                              sys_time_us=3000.0, is_calibrated=1)

            srv.notify_fields("Broadcast", counter=n,
                              driver_attention=0, large_vehicles=1,
                              dangerous_vehicle=0, pedestrians=1)

            srv.notify_fields("PilotStatus", counter=n,
                              ACCStatus=1, ICCStatus=1, DNPStatus=0,
                              TakeoverStatus=0, driving_time=n * 100)

            srv.notify_fields("PilotAlarm", counter=n,
                              PilotAlarmReason=1, alarm_distance=50, alarm_stage=2,
                              alarm_timestamp=123456.0, PilotNotice=1,
                              notice_distance=100, notice_timestamp=123457.0)

            srv.notify_fields("ChangeLane", counter=n,
                              ChangeLaneState=1, ChangeLaneDirection=2,
                              is_change_safety=1, ChangeLane_timestamp=0x11223344,
                              change_ratio=0.5, change_termi=0,
                              landing_center_X=10.0, landing_center_Y=0.0,
                              landing_center_Z=0.0, landing_box_length=4.0,
                              landing_box__width=1.8, landing_box_height=1.5)

            srv.notify_fields("HudMappath", counter=n,
                              is_on_the_path=1, road_angle=15, road_slope=0.03,
                              all_EHP_v2_info="EHP-DEMO-2025")

            srv.notify_fields("HudNavmap", counter=n,
                              Navigation_map="NAV-MAP-2025-06-25")

            _, _, payload = srv.notify_fields(
                "VehiclePosition", counter=n,
                Longitude=116.397, Latitude=39.908, altitude=50.0, Heading=90.0,
                hd_lane_left_angle=1.0, Hd_lane_right_angle=-1.0, VehicleSpeed=60.0,
                acceleration=0.5, x_speed=1.0, y_speed=0.0, z_speed=0.0,
                timestamp=0x12345678, hd_link_id=100, hd_lane_id=2, hd_lane_type=1,
                on_lane_offset=0.1, hd_lane_seq=3, hd_lane_num=4,
                hd_lane_left_lateral_offset=1.5, hd_lane_right_lateral_offset=1.5,
                roll=0.0, pitch=0.0, HdStatus=1, hdmap_version=1, fusion_status=2,
                pos_confidence=0.99, position_type=0, break_light=0,
                indicator_light=1, Lights=1, Weather=0, target_cruise_speed=80.0,
                lanes=[1, 2, 3], segs=[10, 20], loc_offset=0)
            print(f"[send] VehiclePosition(0x{svc:04X}/0x{ev:04X}) #{n} len={len(payload)}", flush=True)

            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[demo] 退出")
    finally:
        srv.close()


if __name__ == "__main__":
    main()
