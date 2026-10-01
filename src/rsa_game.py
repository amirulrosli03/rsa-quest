import time
import json
import os
import math
import secrets
from dataclasses import dataclass
from typing import List, Tuple, Callable, Any, Optional

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)

LEADERBOARD_FILE = os.path.join(DATA_DIR, "leaderboard.json")


# ---------- RSA / Math Helpers ----------
def egcd(a: int, b: int):
    if b == 0:
        return a, 1, 0
    g, x1, y1 = egcd(b, a % b)
    return g, y1, x1 - (a // b) * y1


def modinv(a: int, m: int) -> int:
    # Python 3.8+ supports pow(a, -1, m) in newer versions; keep fallback too.
    try:
        return pow(a, -1, m)
    except TypeError:
        g, x, _ = egcd(a, m)
        if g != 1:
            raise ValueError("No modular inverse exists.")
        return x % m


def is_probable_prime(n: int, k: int = 8) -> bool:
    """Miller-Rabin primality test (probabilistic). Good enough for a game."""
    if n < 2:
        return False
    small_primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    if n in small_primes:
        return True
    if any(n % p == 0 for p in small_primes):
        return False

    # write n-1 as d*2^s
    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1

    for _ in range(k):
        a = secrets.randbelow(n - 3) + 2  # [2, n-2]
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for __ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def random_odd_in_range(lo: int, hi: int) -> int:
    x = secrets.randbelow(hi - lo + 1) + lo
    if x % 2 == 0:
        x += 1
    if x > hi:
        x -= 2
    return x


def generate_prime(digits: int) -> int:
    lo = 10 ** (digits - 1)
    hi = (10 ** digits) - 1
    if digits <= 1:
        lo, hi = 11, 97
    while True:
        cand = random_odd_in_range(lo, hi)
        if is_probable_prime(cand):
            return cand


def make_candidates(digits: int, total: int = 10, prime_count: int = 6) -> List[int]:
    primes = [generate_prime(digits) for _ in range(prime_count)]
    comps = []
    while len(comps) < (total - prime_count):
        a = secrets.randbelow(90) + 10
        b = secrets.randbelow(90) + 10
        c = a * b
        if len(str(c)) == digits and not is_probable_prime(c):
            comps.append(c)
    nums = primes + comps
    secrets.SystemRandom().shuffle(nums)
    return nums


def candidate_es(phi: int, count: int = 7) -> List[int]:
    base = [3, 5, 17, 257, 65537, 7, 11, 13, 19, 23]
    valid = [e for e in base if 1 < e < phi and math.gcd(e, phi) == 1]

    e = 3
    while len(valid) < count and e < min(phi, 500):
        if math.gcd(e, phi) == 1:
            valid.append(e)
        e += 2

    seen = []
    for x in valid:
        if x not in seen:
            seen.append(x)
    return seen[:count]


# ---------- Game Config ----------
@dataclass
class Difficulty:
    name: str
    prime_digits: int
    stage_time_limit: float  # seconds per stage/prompt


DIFFS = {
    "1": Difficulty("Easy", prime_digits=3, stage_time_limit=60.0),
    "2": Difficulty("Medium", prime_digits=4, stage_time_limit=45.0),
    "3": Difficulty("Hard", prime_digits=5, stage_time_limit=35.0),
}


# ---------- UI Helpers ----------
def print_summary_card(title: str, lines: List[str]):
    width = max(len(title) + 6, *(len(x) + 4 for x in lines), 36)
    print("\n" + "┌" + "─" * (width - 2) + "┐")
    print("│" + f"  {title}  ".center(width - 2) + "│")
    print("├" + "─" * (width - 2) + "┤")
    for line in lines:
        print("│ " + line.ljust(width - 3) + "│")
    print("└" + "─" * (width - 2) + "┘")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    while True:
        suffix = " (Y/n): " if default else " (y/N): "
        ans = input(prompt + suffix).strip().lower()
        if ans == "":
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("Please type y or n 🙂")


def timed_input_validated(
    prompt: str,
    limit_sec: float,
    validator: Callable[[str], Any],
) -> Tuple[Any, float, int]:
    """
    Returns: (validated_value, elapsed_time, mistakes_count)
    mistakes_count increments each time user enters invalid input and is reprompted.
    """
    start = time.perf_counter()
    mistakes = 0

    while True:
        elapsed = time.perf_counter() - start
        remaining = limit_sec - elapsed
        if remaining <= 0:
            raise TimeoutError("⏰ Time's up!")

        raw = input(f"{prompt} (remaining {remaining:.1f}s): ")
        elapsed = time.perf_counter() - start
        if elapsed > limit_sec:
            raise TimeoutError("⏰ Time's up!")

        try:
            value = validator(raw)
            return value, elapsed, mistakes
        except Exception as e:
            mistakes += 1
            print(f"❌ {e}")
            # loop continues until time runs out or valid


# ---------- Leaderboard ----------
def load_board():
    if not os.path.exists(LEADERBOARD_FILE):
        return []
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_board(entries):
    with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def update_board(player_name: str, difficulty: str, total_time: float) -> Tuple[int, bool]:
    """
    Returns (rank, is_champion)
    """
    board = load_board()
    run_id = secrets.token_hex(4)
    entry = {
        "id": run_id,
        "name": player_name,
        "difficulty": difficulty,
        "time_sec": round(total_time, 3),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    board.append(entry)
    board.sort(key=lambda x: x["time_sec"])
    board = board[:10]
    save_board(board)

    rank = next((i for i, row in enumerate(board, 1) if row.get("id") == run_id), 999)
    is_champion = (rank == 1)
    return rank, is_champion


def show_board():
    board = load_board()
    print("\n🏆 LEADERBOARD (Top 10 Fastest)")
    if not board:
        print("  (empty) Be the first! 😄")
        return
    for i, row in enumerate(board, 1):
        print(f"  {i:>2}. {row['name']} | {row['difficulty']} | {row['time_sec']}s | {row['timestamp']}")


# ---------- Game Stages ----------
def stage1_prime_selection(diff: Difficulty, explain: bool) -> Tuple[int, int, float, int]:
    print("\n=== Stage 1: Prime Number Selection ===")
    print("Pick TWO primes (p and q) from the list.")
    print("👉 You can enter either the INDEX (e.g., 7) OR the NUMBER itself (e.g., 351).")

    if explain:
        print("\n💡 Hint/Explain:")
        print("• RSA starts by choosing two prime numbers p and q.")
        print("• Primes are important because factoring n = p×q is hard (that’s the security idea).")

    candidates = make_candidates(diff.prime_digits, total=10, prime_count=6)
    for idx, val in enumerate(candidates, 1):
        print(f"  [{idx}] {val}")

    def parse_choice(raw: str) -> int:
        raw = raw.strip()
        if not raw.isdigit():
            raise ValueError("Enter a number (index or value).")
        x = int(raw)
        if 1 <= x <= len(candidates):
            return candidates[x - 1]  # index
        if x in candidates:
            return x  # value
        raise ValueError("Not in the list. Enter a valid index or a listed value.")

    p, t1, m1 = timed_input_validated("Choose p", diff.stage_time_limit, parse_choice)
    q, t2, m2 = timed_input_validated("Choose q", diff.stage_time_limit, parse_choice)

    if p == q:
        raise ValueError("p and q must be different.")
    if not is_probable_prime(p) or not is_probable_prime(q):
        raise ValueError("One (or both) selected numbers are NOT prime!")

    stage_time = max(t1, t2)  # "time used" perception for stage 1
    mistakes = m1 + m2

    print("✅ Prime selection complete!")
    print_summary_card(
        "Stage 1 Summary ✅",
        [
            f"p = {p}",
            f"q = {q}",
            f"Mistakes (retries): {mistakes}",
            f"Time used (approx): {stage_time:.2f}s",
        ],
    )
    return p, q, stage_time, mistakes


def stage2_key_generation(p: int, q: int, diff: Difficulty, explain: bool) -> Tuple[int, int, int, int, float, int]:
    print("\n=== Stage 2: Key Pair Generation ===")
    n = p * q
    phi = (p - 1) * (q - 1)

    if explain:
        print("\n💡 Hint/Explain:")
        print("• n = p×q is used in both public & private keys.")
        print("• φ(n) = (p−1)(q−1) is used to build the keys.")
        print("• We choose e such that gcd(e, φ(n)) = 1, so the inverse d exists.")

    print(f"Computed n = p*q = {n}")
    print(f"Computed φ(n) = (p-1)(q-1) = {phi}")

    options = candidate_es(phi, count=7)
    print("\nChoose public exponent e (must satisfy gcd(e, φ(n))=1):")
    for idx, e in enumerate(options, 1):
        print(f"  [{idx}] e = {e}")

    def parse_e(raw: str) -> int:
        raw = raw.strip()
        if not raw.isdigit():
            raise ValueError("Enter a number (index or value).")
        x = int(raw)
        if 1 <= x <= len(options):
            return options[x - 1]
        if x in options:
            return x
        raise ValueError("Not in the options list.")

    e, elapsed, mistakes = timed_input_validated("Choose e", diff.stage_time_limit, parse_e)

    if math.gcd(e, phi) != 1:
        raise ValueError("Selected e is not coprime with φ(n).")

    d = modinv(e, phi)

    print("✅ Key generation complete!")
    print_summary_card(
        "Stage 2 Summary ✅",
        [
            f"n   = {n}",
            f"phi = {phi}",
            f"e   = {e}",
            f"d   = {d}",
            f"Mistakes (retries): {mistakes}",
            f"Time used: {elapsed:.2f}s",
        ],
    )
    return n, phi, e, d, elapsed, mistakes


def stage3_encrypt(n: int, e: int, diff: Difficulty, explain: bool) -> Tuple[str, List[int], float, int]:
    print("\n=== Stage 3: Encryption ===")

    if explain:
        print("\n💡 Hint/Explain:")
        print("• Each character becomes a number using ASCII (ord).")
        print("• Encryption uses: C = M^e mod n")
        print("• Important: M must be < n (so ASCII values must be smaller than n).")

    def validate_message(raw: str) -> str:
        msg = raw  # allow spaces
        if msg == "":
            raise ValueError("Message cannot be empty.")
        nums = [ord(ch) for ch in msg]
        if any(m >= n for m in nums):
            raise ValueError("Some ASCII values are >= n. Use shorter message or higher difficulty.")
        return msg

    msg, elapsed, mistakes = timed_input_validated("Enter plaintext", diff.stage_time_limit, validate_message)

    cipher = [pow(ord(ch), e, n) for ch in msg]
    print("\n✅ Encrypted message (integers):")
    print("  " + " ".join(map(str, cipher)))

    print_summary_card(
        "Stage 3 Summary ✅",
        [
            f"Plaintext length: {len(msg)} chars",
            f"Ciphertext length: {len(cipher)} ints",
            f"Mistakes (retries): {mistakes}",
            f"Time used: {elapsed:.2f}s",
        ],
    )
    return msg, cipher, elapsed, mistakes


def stage4_decrypt(n: int, d: int, cipher: List[int], original: str, diff: Difficulty, explain: bool) -> Tuple[float, int]:
    print("\n=== Stage 4: Decryption ===")
    print("Ciphertext:")
    print("  " + " ".join(map(str, cipher)))

    if explain:
        print("\n💡 Hint/Explain:")
        print("• Decryption uses: M = C^d mod n")
        print("• If d is correct, the decrypted text should match the original.")

    def validate_d(raw: str) -> int:
        raw = raw.strip()
        if not raw.lstrip("-").isdigit():
            raise ValueError("d must be an integer.")
        user_d = int(raw)
        if user_d != d:
            raise ValueError("Wrong d. Try again.")
        return user_d

    _user_d, elapsed, mistakes = timed_input_validated("Enter private key d", diff.stage_time_limit, validate_d)

    plain_nums = [pow(c, d, n) for c in cipher]
    decrypted = "".join(chr(x) for x in plain_nums)

    print(f"\n✅ Decrypted message: {decrypted}")
    if decrypted != original:
        raise ValueError("Decryption mismatch (does not match original).")

    print("🎉 Correct! Decryption matches the original message.")
    print_summary_card(
        "Stage 4 Summary ✅",
        [
            f"Decrypted OK ✅",
            f"Mistakes (retries): {mistakes}",
            f"Time used: {elapsed:.2f}s",
        ],
    )
    return elapsed, mistakes


# ---------- Achievements ----------
def compute_achievements(
    success: bool,
    total_time: float,
    difficulty_name: str,
    total_mistakes: int,
    is_champion: bool,
) -> List[str]:
    if not success:
        return []

    badges = []
    if total_time < 30.0:
        badges.append("⚡ Speedrunner — finished under 30 seconds")
    if total_mistakes == 0:
        badges.append("✅ Perfect Run — zero retries / zero invalid inputs")
    if difficulty_name.lower() == "hard":
        badges.append("🥷 Hardcore — won on Hard difficulty")
    if is_champion:
        badges.append("👑 Champion — #1 on the leaderboard")
    return badges


def show_achievements(badges: List[str]):
    print("\n🎖️ ACHIEVEMENTS")
    if not badges:
        print("  (none this run) — try faster / harder / fewer mistakes 😄")
        return
    for b in badges:
        print(f"  • {b}")


#  One Play Session (single run) 
def play_session():
    print("🔐 Welcome to RSA QUEST: Escape the Cipher Vault! 🔐")
    print("Goal: clear all RSA stages under time pressure and get on the leaderboard.\n")

    name = input("Player name: ").strip() or "Player"
    explain_mode = ask_yes_no("Enable Explain/Hint Mode?", default=True)

    print("\nChoose difficulty:")
    print("  [1] Easy   (3-digit primes, 60s per prompt)")
    print("  [2] Medium (4-digit primes, 45s per prompt)")
    print("  [3] Hard   (5-digit primes, 35s per prompt)")
    diff_choice = input("Your choice (1/2/3): ").strip()
    diff = DIFFS.get(diff_choice, DIFFS["1"])

    print(f"\n✅ Difficulty selected: {diff.name}")
    print(f"✅ Explain mode: {'ON' if explain_mode else 'OFF'}")
    print("Tip: Faster + fewer mistakes = more achievements 🏁\n")

    total_start = time.perf_counter()
    total_mistakes = 0

    # track stage timing if you want to show at end
    stage_times = {}

    try:
        p, q, t1, m1 = stage1_prime_selection(diff, explain_mode)
        total_mistakes += m1
        stage_times["Stage 1"] = t1

        n, phi, e, d, t2, m2 = stage2_key_generation(p, q, diff, explain_mode)
        total_mistakes += m2
        stage_times["Stage 2"] = t2

        original, cipher, t3, m3 = stage3_encrypt(n, e, diff, explain_mode)
        total_mistakes += m3
        stage_times["Stage 3"] = t3

        t4, m4 = stage4_decrypt(n, d, cipher, original, diff, explain_mode)
        total_mistakes += m4
        stage_times["Stage 4"] = t4

        total_time = time.perf_counter() - total_start
        print(f"\n⏱️ Total completion time: {total_time:.3f}s")

        # Leaderboard update (same as before: top 10 by time)
        rank, is_champion = update_board(name, diff.name, total_time)
        show_board()

        # Achievements
        badges = compute_achievements(
            success=True,
            total_time=total_time,
            difficulty_name=diff.name,
            total_mistakes=total_mistakes,
            is_champion=is_champion,
        )
        show_achievements(badges)

        # Final run summary card
        print_summary_card(
            "Run Summary ✅",
            [
                f"Player: {name}",
                f"Difficulty: {diff.name}",
                f"Explain mode: {'ON' if explain_mode else 'OFF'}",
                f"Total time: {total_time:.3f}s",
                f"Total mistakes (retries): {total_mistakes}",
                f"Leaderboard rank: #{rank if rank != 999 else 'N/A'}",
            ],
        )

        return True

    except Exception as ex:
        total_time = time.perf_counter() - total_start
        print("\n💥 GAME OVER!")
        print(f"Reason: {ex}")
        print(f"Your run time before failing: {total_time:.3f}s")
        show_board()

        print_summary_card(
            "Run Summary ❌",
            [
                f"Player: {name}",
                f"Difficulty: {diff.name}",
                f"Explain mode: {'ON' if explain_mode else 'OFF'}",
                f"Time before fail: {total_time:.3f}s",
                f"Mistakes (retries): {total_mistakes}",
            ],
        )
        return False


# ---------- Main Loop (auto restart) ----------
def main():
    while True:
        print("\n" + "=" * 60)
        play_session()
        if not ask_yes_no("\nPlay again?", default=True):
            print("\nThanks for playing! 👋")
            break


if __name__ == "__main__":
    main()
