@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 관리자는 검열 및 도배 감지에서 제외
    if message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    # 1. 비속어 검열 처리 (경고 메시지 출력 후 3초 뒤 자동 삭제)
    if is_bad_word(message.content):
        try:
            await message.delete()
        except discord.NotFound:
            pass

        # 채널에 경고 메시지 작성
        warning_msg = await message.channel.send(
            f"⚠️ {message.author.mention}님, 부적절한 언행(초성, 성적/혐오/비하 표현, 영문 욕설 등)은 제한됩니다!"
        )
        
        # 3초 대기 후 경고 메시지 삭제
        await asyncio.sleep(3)
        try:
            await warning_msg.delete()
        except discord.NotFound:
            pass
        return

    # 2. 도배 및 스팸 감지 (도배 경고 메시지 출력 후 5초 뒤 자동 삭제)
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
                await message.author.timeout(timedelta(minutes=5), reason="도배 및 스팸 행위 자동 감지")
                user_spam_records[author_id] = {"timestamps": [], "messages": []}

                spam_msg = await message.channel.send(
                    f"🚫 {message.author.mention}님, 도배 행위가 감지되어 **5분간 타임아웃**되었습니다."
                )

                try:
                    await message.delete()
                except discord.NotFound:
                    pass

                # 도배 경고는 5초 대기 후 삭제
                await asyncio.sleep(5)
                try:
                    await spam_msg.delete()
                except discord.NotFound:
                    pass
                return
            except Exception as e:
                print(f"타임아웃 실행 중 오류 발생: {e}")

    await bot.process_commands(message)
