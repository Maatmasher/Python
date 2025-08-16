PLINK_CMD = "plink.exe -ssh {user}@{host} -pw {password} -batch -m {command_txt}"


async def _run_plink(host):
    """Асинхронное выполнение команды через plink"""
    cmd = PLINK_CMD.format(
        user=USER, password=PASSWORD, command_txt=COMMAND_FILE, host=host
    )
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)
            stdout = stdout.decode().strip()
            stderr = stderr.decode().strip()

            if proc.returncode == 0:
                await log_message(f"{host}  Команды выполнены успешно\n{stdout}")
            else:
                await log_message(
                    f"{host}  Ошибка выполнения команд (код {proc.returncode})\n{stderr}"
                )
        except asyncio.TimeoutError:
            await log_message(f"{host}  Таймаут выполнения команд")
            proc.kill()
            await proc.communicate()
    except Exception as e:
        await log_message(f"{host}  Критическая ошибка при выполнении команд: {str(e)}")
