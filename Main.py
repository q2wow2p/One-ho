import os
import re
import time
import json
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("슬래시 명령어 동기화 완료!")

bot = MyBot()

# ---------------------------------------------------------
# [레벨링 시스템 데이터 관리]
# ---------------------------------------------------------
LEVEL_FILE = "levels.json"
user_xp_cooldown = {} # XP 획득 쿨타임 (1분)

def load_level_data():
    if os.path.exists(LEVEL_FILE):
        try:
            with open(LEVEL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_level_data(data):
    try:
        with open(LEVEL_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"데이터 저장 오류: {e}")

# ---------------------------------------------------------
# [통합 차단 단어 목록]
# ---------------------------------------------------------
BAD_WORDS = [
    "씨발", "시발", "개새끼", "병신", "좆", "지랄", "존나", "닥쳐", "애미", "애비", "느금마",
    "ㅅㅂ", "ㅂㅅ", "ㅈ까", "씨바", "븅신", "썅", "시불", "느금", "엠창", "떵개", "꺼져", "ㅆㅂ", "ㄴㄱㅁ", "ㄱㅅㄲ", "ㅈㄹ",
    "시이불", "지이랄", "니엄마", "느엄마", "니애미", "느애미",
    "sex", "섹스", "자지", "보지", "야동", "야짤", "조건만남", "몸캠", "자위", "정액", "강간",
    "쎅스", "섺스",
    "한남충", "메갈", "틀딱", "맘충", "급식충", "짱깨", "쪽발이", "애자",
    "장애", "장애자", "장애인", "장애우",
    "fuck", "shit", "bitch", "asshole", "dick", "pussy", "cunt", "nigger", "porn"
]

def is_bad_word(text: str) -> bool:
    if not text:
        return False

    text_lower = text.lower()

    for bad in BAD_WORDS:
        bad_lower = bad.lower()
        if not bad_lower:
            continue

        # 1. 단어 글자 사이에 모든 문자(숫자, 특수문자, 공백 등) 0~5개가 들어가는 패턴 생성
        # 예: "씨발" -> '씨' + (아무 문자 0~5개) + '발'
        pattern_str = r".{0,5}".join(re.escape(char) for char in bad_lower)

        try:
            if re.search(pattern_str, text_lower, re.IGNORECASE):
                return True
        except re.error:
            pass

    return False

# ---------------------------------------------------------
# [유저별 도배/스팸 감지용 저장소]
# ---------------------------------------------------------
user_spam_records = {}

@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user.name}")

async def check_and_clean_nickname(member: discord.Member):
    if member.bot or member == member.guild.owner:
        return

    name_to_check = member.nick or member.name

    if is_bad_word(name_to_check):
        try:
            new_nick = "부적절한닉네임_리셋"
            await member.edit(nick=new_nick, reason="부적절한 닉네임 자동 감지 및 변경")
        except discord.Forbidden:
            print(f"❌ {member.display_name}님의 닉네임을 변경할 권한이 없습니다.")
        except discord.HTTPException as e:
            print(f"HTTP 오류 발생: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    await check_and_clean_nickname(member)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.nick != after.nick or before.name != after.name:
        await check_and_clean_nickname(after)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 1. 비속어 검열 처리 (숫자/특수문자 포함 변형 표현 감지)
    if is_bad_word(message.content):
        try:
            await message.delete()
        except discord.HTTPException:
            pass

        await asyncio.sleep(0.2)

        try:
            warning_msg = await message.channel.send(
                f"⚠️ {message.author.mention}님, 부적절한 언행(숫자/특수문자 변형 표현 포함)은 제한되며 **경험치가 지급되지 않습니다!**"
            )
            await asyncio.sleep(3)
            await warning_msg.delete()
        except discord.HTTPException:
            pass
        return  # ❌ 욕설 감지 시 XP 지급 절차 차단

    # 2. 도배 및 스팸 감지
    author_id = message.author.id
    current_time = time.time()

    if author_id not in user_spam_records:
        user_spam_records[author_id] = {"timestamps": [], "messages": []}

    record = user_spam_records[author_id]
    record["timestamps"].append(current_time)
    record["messages"].append(message.content)

    if len(record["timestamps"]) > 10:
        record["timestamps"].pop(0)
        record["messages"].pop(0)

    if len(record["timestamps"]) == 10:
        intervals = [record["timestamps"][i] - record["timestamps"][i-1] for i in range(1, 10)]
        base_interval = intervals[0]
        
        is_regular_macro = all(abs(interval - base_interval) <= 0.6 for interval in intervals) and (0.5 <= base_interval <= 300.0)
        total_duration = record["timestamps"][-1] - record["timestamps"][0]
        is_fast_spam = total_duration <= 15.0 
        all_same_content = all(msg == record["messages"][0] for msg in record["messages"])

        if is_regular_macro or is_fast_spam or all_same_content:
            try:
                from datetime import timedelta
                if message.author != message.guild.owner:
                    await message.author.timeout(timedelta(minutes=5), reason="도배 및 스팸 행위 자동 감지")
                
                user_spam_records[author_id] = {"timestamps": [], "messages": []}

                await asyncio.sleep(0.2)
                spam_msg = await message.channel.send(
                    f"🚫 {message.author.mention}님, 도배 행위가 감지되어 **5분간 타임아웃**되었습니다."
                )

                try:
                    await message.delete()
                except discord.HTTPException:
                    pass

                await asyncio.sleep(5)
                try:
                    await spam_msg.delete()
                except discord.HTTPException:
                    pass
                return
            except Exception as e:
                print(f"도배 처리 중 오류 발생: {e}")

    # 3. 레벨링 및 경험치(XP) 지급 처리
    user_str_id = str(author_id)
    last_xp_time = user_xp_cooldown.get(user_str_id, 0)

    if current_time - last_xp_time > 60:
        user_xp_cooldown[user_str_id] = current_time
        level_data = load_level_data()

        if user_str_id not in level_data:
            level_data[user_str_id] = {"xp": 0, "level": 1}

        gained_xp = random.randint(15, 25)
        level_data[user_str_id]["xp"] += gained_xp

        current_xp = level_data[user_str_id]["xp"]
        current_lvl = level_data[user_str_id]["level"]
        needed_xp = current_lvl * 100

        if current_xp >= needed_xp:
            level_data[user_str_id]["level"] += 1
            level_data[user_str_id]["xp"] -= needed_xp
            new_lvl = level_data[user_str_id]["level"]

            try:
                lvl_up_msg = await message.channel.send(
                    f"🎉 {message.author.mention}님 축하합니다! **레벨 {new_lvl}**(으)로 레벨업 하셨습니다!"
                )
                await asyncio.sleep(5)
                await lvl_up_msg.delete()
            except discord.HTTPException:
                pass

        save_level_data(level_data)

    await bot.process_commands(message)

# ---------------------------------------------------------
# [/레벨 - 내 현재 레벨 및 XP 확인 슬래시 명령어]
# ---------------------------------------------------------
@bot.tree.command(name="레벨", description="나의 현재 레벨과 경험치를 확인합니다.")
async def show_level(interaction: discord.Interaction):
    level_data = load_level_data()
    user_str_id = str(interaction.user.id)

    if user_str_id not in level_data:
        lvl = 1
        xp = 0
    else:
        lvl = level_data[user_str_id]["level"]
        xp = level_data[user_str_id]["xp"]

    needed_xp = lvl * 100
    await interaction.response.send_message(
        f"📊 **{interaction.user.display_name}**님의 레벨 정보\n"
        f"• **레벨**: Level {lvl}\n"
        f"• **경험치**: {xp} / {needed_xp} XP",
        ephemeral=True
    )

# ---------------------------------------------------------
# [/구간청소 - 시작/끝 메시지 지정 삭제 (점장 / 부점장 전용)]
# ---------------------------------------------------------
@bot.tree.command(name="구간청소", description="시작 메시지와 끝 메시지를 지정하여 특정 구간을 삭제합니다.")
@app_commands.describe(
    시작_메시지_링크="삭제할 시작(오래된) 메시지의 링크를 입력해 주세요.",
    끝_메시지_링크="삭제할 끝(최신) 메시지의 링크를 입력해 주세요."
)
async def purge_range(interaction: discord.Interaction, 시작_메시지_링크: str, 끝_메시지_링크: str):
    allowed_roles = ["오락실 점장", "오락실 부점장"]
    user_role_names = [role.name for role in interaction.user.roles]
    if not any(role in user_role_names for role in allowed_roles):
        await interaction.response.send_message("❌ 이 기능은 **오락실 점장** 또는 **오락실 부점장** 역할만 사용할 수 있습니다!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        start_id = int(시작_메시지_링크.strip().split('/')[-1])
        end_id = int(끝_메시지_링크.strip().split('/')[-1])
    except ValueError:
        await interaction.followup.send("❌ 올바른 메시지 링크 형식이 아닙니다. '메시지 링크 복사'로 가져온 링크를 입력해 주세요.", ephemeral=True)
        return

    try:
        start_msg = await interaction.channel.fetch_message(start_id)
        end_msg = await interaction.channel.fetch_message(end_id)
    except discord.NotFound:
        await interaction.followup.send("❌ 해당 채널에서 시작 또는 끝 메시지를 찾을 수 없습니다.", ephemeral=True)
        return

    if start_msg.created_at > end_msg.created_at:
        start_msg, end_msg = end_msg, start_msg

    try:
        deleted = await interaction.channel.purge(
            after=start_msg.created_at,
            before=end_msg.created_at,
            oldest_first=False
        )
        
        try:
            await start_msg.delete()
        except discord.NotFound:
            pass
        try:
            await end_msg.delete()
        except discord.NotFound:
            pass

        total_deleted = len(deleted) + 2
        await interaction.followup.send(f"🧹 지정한 특정 구간에서 총 **{total_deleted}개**의 메시지를 지웠습니다!", ephemeral=True)

    except discord.HTTPException as e:
        if getattr(e, 'code', None) == 50034 or "14 days" in str(e):
            await interaction.followup.send("⚠️ 선택한 구간에 **14일이 지난 메시지**가 포함되어 있습니다. 14일이 지난 메시지는 디스코드 정책상 한 번에 삭제할 수 없습니다.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ 삭제 중 오류가 발생했습니다: {e}", ephemeral=True)

bot.run(os.environ.get("BOT_TOKEN"))
