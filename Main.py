import os
import re
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
# [정밀 패드립 & 비속어 정규식 패턴]
# ---------------------------------------------------------
PARENT_WORDS = r"(니|네|느|너희|너네|애)[^\w\s]{0,3}(엄마|어머니|아빠|아버지|애미|애비|금마|엠|금)"
PARENT_DIRECT = r"(엄마|어머니|아빠|아버지|애미|애비)"
MOCK_WORDS = r"(뒤진|없|창녀|창놈|레전드|클라스|안계시|뒈진|보지|자지|병신|디진|터짐|터진|갈림|뒈짐)"

RAW_PATTERNS = [
    r"느[^\w\s]{0,3}금",
    PARENT_WORDS,
    rf"{PARENT_DIRECT}[^\w\s]{{0,5}}{MOCK_WORDS}",
    rf"{MOCK_WORDS}[^\w\s]{{0,5}}{PARENT_DIRECT}",
    r"ㄴ[^\w\s]{0,3}ㄱ[^\w\s]{0,3}ㅁ",
    r"ㄴ[^\w\s]{0,3}ㅇ[^\w\s]{0,3}ㅁ",
    r"(시|씨|싔|ㅅㅣ)[^\w\s]{0,3}(발|팔|바|빨|불)",
    r"(개)[^\w\s]{0,3}(새|색|샊)[^\w\s]{0,3}(끼|기|키)",
    r"(병|뼝)[^\w\s]{0,3}(신|씬)",
    r"(지)[^\w\s]{0,3}(랄|럴)",
    r"(존)[^\w\s]{0,3}(나|낙|내)",
    r"(ㅅ|ㅆ)[^\w\s]{0,3}(ㅂ|ㅃ)",
    r"ㅂ[^\w\s]{0,3}ㅅ",
    r"ㄱ[^\w\s]{0,3}ㅅ[^\w\s]{0,3}ㄲ",
    r"ㅈ[^\w\s]{0,3}ㄹ"
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in RAW_PATTERNS]

# ---------------------------------------------------------
# [차단 단어 목록 (욕설, 성적 표현, 혐오 표현, 영문)]
# ---------------------------------------------------------
BAD_WORDS = [
    # 욕설
    "씨발", "시발", "개새끼", "병신", "좆", "지랄", "존나", "닥쳐", "애미", "애비", "느금마",
    "ㅅㅂ", "ㅂㅅ", "ㅈ까", "씨바", "븅신", "썅", "시불", "느금", "엠창", "떵개", "꺼져", "ㅆㅂ", "ㄴㄱㅁ", "ㄱㅅㄲ", "ㅈㄹ",
    
    # 성적 표현
    "섹스", "자지", "보지", "야동", "야짤", "조건만남", "몸캠", "자위", "정액", "강간",
    "쎅스", "섺스", "야동",
    
    # 혐오 표현 (장애 관련 표현 추가)
    "한남충", "메갈", "틀딱", "맘충", "급식충", "짱깨", "쪽발이", "애자",
    "장애", "장애자", "장애인", "장애우", "병신",
    
    # 영문
    "fuck", "shit", "bitch", "asshole", "dick", "pussy", "cunt", "nigger", "porn"
]

def is_bad_word(text: str) -> bool:
    if not text:
        return False
    
    # 1. 특수문자, 공백, 숫자 등을 모두 제거하여 텍스트 압축
    clean_text = re.sub(r"[^\w]", "", text).lower()

    # 2. 지정된 단어 목록(BAD_WORDS) 검사
    for bad in BAD_WORDS:
        clean_bad = re.sub(r"[^\w]", "", bad).lower()
        if clean_bad and clean_bad in clean_text:
            return True

    # 3. 정규식 패턴 검사
    for pattern in COMPILED_PATTERNS:
        if pattern.search(clean_text) or pattern.search(text):
            return True

    return False

@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user.name}")

# ---------------------------------------------------------
# [닉네임 검열 공통 처리 함수]
# ---------------------------------------------------------
async def check_and_clean_nickname(member: discord.Member):
    if member.bot or member == member.guild.owner:
        return

    name_to_check = member.nick or member.name

    if is_bad_word(name_to_check):
        try:
            new_nick = "부적절한닉네임_리셋"
            await member.edit(nick=new_nick, reason="부적절한 닉네임 자동 감지 및 변경")
            
            try:
                await member.send(
                    f"⚠️ **{member.guild.name}** 서버 안내\n"
                    f"사용하신 닉네임(`{name_to_check}`)에 부적절한 단어(혐오/비하 표현 등)가 포함되어 있어 **`{new_nick}`**(으)로 강제 변경되었습니다.\n"
                    f"서버 규정에 맞는 닉네임으로 수정해 주세요!"
                )
            except discord.Forbidden:
                pass

        except discord.Forbidden:
            print(f"❌ {member.display_name}님의 닉네임을 변경할 권한이 없습니다. (봇 역할 순위 확인 필요)")

# ---------------------------------------------------------
# [이벤트: 신규 유저 입장 시 닉네임 검열]
# ---------------------------------------------------------
@bot.event
async def on_member_join(member: discord.Member):
    await check_and_clean_nickname(member)

# ---------------------------------------------------------
# [이벤트: 기존 유저 닉네임/프로필 변경 시 검열]
# ---------------------------------------------------------
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.nick != after.nick or before.name != after.name:
        await check_and_clean_nickname(after)

# ---------------------------------------------------------
# [비속어 감지 및 자동 삭제 (채팅)]
# ---------------------------------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if is_bad_word(message.content):
        await message.delete()
        warning_msg = await message.channel.send(
            f"⚠️ {message.author.mention}님, 부적절한 언행(초성, 성적/혐오/비하 표현, 영문 욕설 등)은 제한됩니다!"
        )
        await warning_msg.delete(delay=3)
        return
    await bot.process_commands(message)

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
