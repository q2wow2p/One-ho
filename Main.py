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
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 봇 실행 전 keep_alive() 호출
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
    r"(시|씨|싔|ㅅㅣ)[^\w\s]{0,3}(발|팔|바|빨)",
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
BAD_WORDS = ["시불", "느금", "엠창", "떵개", "꺼져", "ㅅㅂ", "ㅆㅂ", "ㄴㄱㅁ", "ㅂㅅ", "ㄱㅅㄲ", "ㅈㄹ"]

def is_bad_word(text: str) -> bool:
    clean_text = text.replace(" ", "").replace("_", "").replace("-", "").replace("~", "").replace(".", "").replace(",", "").lower()
    for bad in BAD_WORDS:
        if bad in clean_text:
            return True
    for pattern in COMPILED_PATTERNS:
        if pattern.search(clean_text):
            return True
    return False

@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user.name}")

# ---------------------------------------------------------
# [비속어 감지 및 자동 삭제]
# ---------------------------------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if is_bad_word(message.content):
        await message.delete()
        warning_msg = await message.channel.send(
            f"⚠️ {message.author.mention}님, 부적절한 언행(초성 욕설, 패드립 및 비속어)은 제한됩니다!"
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

    # 1. 메시지 ID 추출
    try:
        start_id = int(시작_메시지_링크.strip().split('/')[-1])
        end_id = int(끝_메시지_링크.strip().split('/')[-1])
    except ValueError:
        await interaction.followup.send("❌ 올바른 메시지 링크 형식이 아닙니다. '메시지 링크 복사'로 가져온 링크를 입력해 주세요.", ephemeral=True)
        return

    # 2. 메시지 불러오기
    try:
        start_msg = await interaction.channel.fetch_message(start_id)
        end_msg = await interaction.channel.fetch_message(end_id)
    except discord.NotFound:
        await interaction.followup.send("❌ 해당 채널에서 시작 또는 끝 메시지를 찾을 수 없습니다.", ephemeral=True)
        return

    # 순서 정리 (더 오래된 메시지를 start_msg로 지정)
    if start_msg.created_at > end_msg.created_at:
        start_msg, end_msg = end_msg, start_msg

    # 3. 구간 삭제 실행 (bulk=True)
    try:
        # start_msg와 end_msg 사이의 메시지 삭제 (시작 및 끝 메시지 포함)
        deleted = await interaction.channel.purge(
            after=start_msg.created_at,
            before=end_msg.created_at,
            oldest_first=False
        )
        
        # 기준이 된 시작 메시지와 끝 메시지 직접 삭제
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
        # 14일 경과 오류(error code 50034) 또는 HTTP 오류 발생 시 안내
        if getattr(e, 'code', None) == 50034 or "14 days" in str(e):
            await interaction.followup.send("⚠️ 선택한 구간에 **14일이 지난 메시지**가 포함되어 있습니다. 14일이 지난 메시지는 디스코드 정책상 한 번에 삭제할 수 없습니다.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ 삭제 중 오류가 발생했습니다: {e}", ephemeral=True)

# 토큰을 코드에 직접 적지 않고, Koyeb의 환경 변수(BOT_TOKEN)에서 가져옵니다.
bot.run(os.environ.get("BOT_TOKEN"))
