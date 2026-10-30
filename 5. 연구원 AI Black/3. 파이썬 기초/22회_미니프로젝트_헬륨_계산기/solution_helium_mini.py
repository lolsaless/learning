"""헬륨 봄베 사용시간 계산기 — 22회 미니 프로젝트 과제 해답

질문에 답하면 사용 가능 시간, 종료 예상 시각, 주 단위 예상 압력을 보여 준다.
Enter만 누르면 [ ] 안의 기본값을 쓴다.

실행 방법 (가상환경을 켠 상태)
    python solution_helium_mini.py
"""

from datetime import datetime, timedelta

P_ATM_PSI = 14.696
TO_PSI = {"psi": 1.0, "bar": 14.5038, "mpa": 145.038, "kpa": 0.145038, "atm": 14.696}


def to_psi(value, unit):
    unit = unit.lower()
    if unit not in TO_PSI:
        raise ValueError(f"지원하지 않는 단위: {unit}")
    return value * TO_PSI[unit]


def usable_gas_l(volume_l, p_in_psi, cutoff_psi):
    return volume_l * max(p_in_psi - cutoff_psi, 0) / P_ATM_PSI


def minutes_left(gas_l, flows):
    total = sum(flows)
    if total <= 0:
        raise ValueError("총 유량은 0보다 커야 합니다.")
    return gas_l * 1000 / total


def fmt_duration(minutes):
    days, rest = divmod(int(round(minutes)), 1440)
    hours, mins = divmod(rest, 60)
    return f"{days}일 {hours}시간 {mins}분"


def weekly_table(volume_l, p_in_psi, flows, total_minutes):
    drop_per_min = sum(flows) / 1000 * P_ATM_PSI / volume_l
    table, week = [], 0
    while week * 10080 <= total_minutes:            # 1주 = 7 × 24 × 60 = 10080분
        table.append((week, p_in_psi - drop_per_min * week * 10080))
        week += 1
    return table


def ask_number(prompt, default):
    """숫자를 입력받는다. 빈 입력이면 기본값, 숫자가 아니면 다시 묻는다."""
    while True:
        text = input(f"{prompt} [{default}]: ").strip()
        if text == "":
            return default
        try:
            return float(text)
        except ValueError:
            print("  숫자를 입력하세요.")


def ask_flows():
    """장비별 유량을 빈 줄이 나올 때까지 입력받는다 (최소 1개)."""
    flows = []
    print("장비별 유량(mL/min)을 입력하세요. 빈 줄이면 입력을 마칩니다.")
    while True:
        text = input(f"  유량 {len(flows) + 1}: ").strip()
        if text == "":
            if flows:
                return flows
            print("  최소 1개는 입력해야 합니다.")
            continue
        try:
            flows.append(float(text))
        except ValueError:
            print("  숫자를 입력하세요.")


def main():
    print("헬륨 봄베 사용 가능 시간 계산기 (Enter = 기본값)")
    unit = input("압력 단위 psi/bar/mpa/kpa/atm [psi]: ").strip().lower() or "psi"
    if unit not in TO_PSI:
        print(f"지원하지 않는 단위입니다: {unit}")
        return
    volume = ask_number("봄베 용적(L)", 47.0)
    p_in = ask_number(f"현재 게이지압({unit})", 600.0)
    p_out = ask_number(f"출구 압력({unit})", 80.0)
    margin = ask_number(f"교체 여유압({unit})", 0.0)
    flows = ask_flows()

    p_in_psi = to_psi(p_in, unit)
    gas = usable_gas_l(volume, p_in_psi, to_psi(p_out + margin, unit))
    minutes = minutes_left(gas, flows)
    end = datetime.now() + timedelta(minutes=minutes)

    print("\n===== 결과 =====")
    print(f"총 유량          : {sum(flows):g} mL/min")
    print(f"사용 가능 가스량 : {gas:.1f} L (1 atm 환산)")
    print(f"사용 가능 시간   : {fmt_duration(minutes)} ({minutes / 1440:.2f} 일)")
    print(f"압력 유지 종료   : {end:%Y-%m-%d %H:%M} 경")
    print("[주 단위 예상 게이지압]")
    for week, p in weekly_table(volume, p_in_psi, flows, minutes):
        print(f"  +{week:>2}주  {p / TO_PSI[unit]:8.1f} {unit}")


if __name__ == "__main__":
    main()
