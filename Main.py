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
# [통합 차단 단어 목록 (@이도, 이도 제거됨)]
# ---------------------------------------------------------
BAD_WORDS = [
    # 욕설 및 변형 표현
    "씨발", "시발", "개새끼", "병신", "좆", "지랄", "존나", "닥쳐", "애미", "애비", "느금마",
    "ㅅㅂ", "ㅂㅅ", "ㅈ까", "씨바", "븅신", "썅", "시불", "느금", "엠창", "떵개", "꺼져", "ㅆㅂ", "ㄴㄱㅁ", "ㄱㅅㄲ", "ㅈㄹ",
    "시이불", "지이랄", "니엄마", "느엄마", "니애미", "느애미",
    
    # 성적 표현
    "섹스", "자지", "보지", "야동", "야짤", "조건만남", "몸캠", "자위", "정액", "강간",
    "쎅스", "섺스",
    
    # 혐오 표현 (장애 관련 표현 포함)
    "한남충", "메갈", "틀딱", "맘충", "급식충", "짱깨", "쪽발이", "애자",
    "장애", "장애자", "장애인", "장애우",
    
    # 영문 욕설 및 은어
    "fuck", "shit", "bitch", "asshole", "dick", "pussy", "cunt", "nigger", "porn"
]

def is_bad_word(text: str) -> bool:
    if not text:
        return False
    
    text_lower = text.lower()
    clean_text = re.sub(r"[^\w@]", "", text_lower)

    for bad in BAD_WORDS:
        bad_lower = bad.lower()
        clean_bad = re.sub(r"[^\w@]", "", bad_lower)
        
        if not clean_bad:
            continue
            
        if clean_bad in clean_text:
            return True
            
        if bad_lower in text_lower:
            return True

        pattern_str = ""
        for char in clean_bad:
            pattern_str += re.escape(char) + r"[^\w\s@]{0,3}"
        
        try:
            if re.search(pattern_str, clean_text, re.IGNORECASE):
                return True
        except re.error:
            pass

    return False

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
    if is_bad_word(message.content):
        await message.delete()
        warning_msg = await message.channel.send(
            f"⚠️ {message.author.mention}님, 부적절한 언행(초성, 성적/혐오/비하 표현, 영문 욕설 등)은 제한됩니다!"
        )
        await warning_msg.delete(delay=3)
        return
    await bot.process_commands(message)

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
