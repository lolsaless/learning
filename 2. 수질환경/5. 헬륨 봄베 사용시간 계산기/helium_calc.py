#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
헬륨 봄베 사용 가능 시간 계산기 (GC-MS / 헤드스페이스용)

봄베 게이지압에서 '출구(레귤레이터 설정) 압력 + 여유압'까지 내려가는 동안
꺼낼 수 있는 가스량을 구해, 총 유량으로 나누어 사용 가능 시간을 계산한다.

사용 예:
    python helium_calc.py                       # 대화형 입력
    python helium_calc.py -i 600 -o 80 -f 50    # 한 줄 실행
    python helium_calc.py -i 600 -o 80 -f 30 -f 20 -m 20 -v 47
"""
import argparse
from datetime import datetime, timedelta

P_ATM_PSI = 14.696  # 1 atm = 14.696 psi

# 단위 -> psi 환산계수
TO_PSI = {
    "psi": 1.0,
    "bar": 14.5038,
    "mpa": 145.038,
    "kpa": 0.145038,
    "atm": 14.696,
}


def calculate(volume_l, p_in, p_out, flows_ml_min, unit="psi", margin=0.0, start=None):
    """
    volume_l      : 봄베 내용적 (L)
    p_in          : 봄베 현재 게이지압
    p_out         : 출구(필요) 압력, 게이지압
    flows_ml_min  : 소비 유량 목록 (mL/min, 대기압 기준) - 합산됨
    unit          : 압력 단위 (psi, bar, mpa, kpa, atm)
    margin        : 교체 여유압 (출구압에 더함, 같은 단위)
    start         : 계산 시작 시각 (기본: 현재)
    """
    unit = unit.lower()
    if unit not in TO_PSI:
        raise ValueError(f"지원하지 않는 단위: {unit}")
    k = TO_PSI[unit]
    p_in_psi = p_in * k
    cutoff_psi = (p_out + margin) * k
    q_total = float(sum(flows_ml_min))

    if volume_l <= 0:
        raise ValueError("봄베 용적은 0보다 커야 합니다.")
    if q_total <= 0:
        raise ValueError("총 유량은 0보다 커야 합니다.")

    start = start or datetime.now()
    usable_psi = max(p_in_psi - cutoff_psi, 0.0)
    usable_l = volume_l * usable_psi / P_ATM_PSI          # 1 atm 환산 가스량 (L)
    minutes = usable_l * 1000.0 / q_total
    end = start + timedelta(minutes=minutes)

    # 주 단위 예상 게이지압 (psi)
    table = []
    week = 0
    while True:
        t_min = week * 7 * 24 * 60
        if t_min > minutes:
            break
        p_psi = p_in_psi - q_total * t_min / 1000.0 * P_ATM_PSI / volume_l
        table.append((week, p_psi / k))
        week += 1

    return {
        "unit": unit,
        "q_total": q_total,
        "cutoff": cutoff_psi / k,
        "usable_psi": usable_psi,
        "usable_l": usable_l,
        "minutes": minutes,
        "hours": minutes / 60.0,
        "days": minutes / 1440.0,
        "start": start,
        "end": end,
        "weekly": table,
    }


def fmt_duration(minutes):
    d, rem = divmod(int(round(minutes)), 1440)
    h, m = divmod(rem, 60)
    return f"{d}일 {h}시간 {m}분"


def print_result(r, volume_l, p_in, p_out, margin):
    u = r["unit"]
    print("\n===== 헬륨 봄베 사용 가능 시간 =====")
    print(f"봄베 용적        : {volume_l:g} L")
    print(f"현재 게이지압    : {p_in:g} {u}")
    print(f"출구압(+여유)    : {p_out:g} (+{margin:g}) = {r['cutoff']:g} {u}")
    print(f"총 유량          : {r['q_total']:g} mL/min")
    print(f"사용 가능 가스량 : {r['usable_l']:.1f} L (1 atm 환산)")
    print(f"사용 가능 시간   : {fmt_duration(r['minutes'])}  "
          f"({r['hours']:.1f} 시간 / {r['days']:.2f} 일)")
    print(f"기준 시각        : {r['start']:%Y-%m-%d %H:%M}")
    print(f"압력 유지 종료   : {r['end']:%Y-%m-%d %H:%M} 경")
    print("\n[주 단위 예상 게이지압]")
    for w, p in r["weekly"]:
        print(f"  +{w:>2}주  {p:8.1f} {u}")


def ask(prompt, default=None, cast=float):
    s = input(f"{prompt}" + (f" [{default}]" if default is not None else "") + ": ").strip()
    if not s and default is not None:
        return default
    return cast(s)


def interactive():
    print("헬륨 봄베 사용 가능 시간 계산기 (Enter = 기본값)")
    unit = ask("압력 단위(psi/bar/mpa/kpa/atm)", "psi", str)
    vol = ask("봄베 용적(L)", 47.0)
    p_in = ask(f"봄베 현재 게이지압({unit})", 600.0)
    p_out = ask(f"출구 압력({unit})", 80.0)
    margin = ask(f"교체 여유압({unit})", 0.0)
    flows = []
    print("소비 유량(mL/min)을 장비별로 입력하세요. 빈 줄이면 종료.")
    i = 1
    while True:
        s = input(f"  유량 {i}: ").strip()
        if not s:
            if flows:
                break
            print("  최소 1개는 입력해야 합니다.")
            continue
        flows.append(float(s))
        i += 1
    return vol, p_in, p_out, flows, unit, margin


def main():
    ap = argparse.ArgumentParser(description="헬륨 봄베 사용 가능 시간 계산기")
    ap.add_argument("-v", "--volume", type=float, default=47.0, help="봄베 용적 L (기본 47)")
    ap.add_argument("-i", "--inlet", type=float, help="봄베 현재 게이지압")
    ap.add_argument("-o", "--outlet", type=float, help="출구(필요) 압력")
    ap.add_argument("-f", "--flow", type=float, action="append",
                    help="유량 mL/min (여러 번 지정하면 합산)")
    ap.add_argument("-u", "--unit", default="psi", choices=list(TO_PSI), help="압력 단위")
    ap.add_argument("-m", "--margin", type=float, default=0.0, help="교체 여유압")
    a = ap.parse_args()

    if a.inlet is None or a.outlet is None or not a.flow:
        vol, p_in, p_out, flows, unit, margin = interactive()
    else:
        vol, p_in, p_out, flows, unit, margin = a.volume, a.inlet, a.outlet, a.flow, a.unit, a.margin

    r = calculate(vol, p_in, p_out, flows, unit, margin)
    print_result(r, vol, p_in, p_out, margin)


if __name__ == "__main__":
    main()
