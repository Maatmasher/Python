PSCP_CMD = "pscp.exe -pw {password} -scp -P 22 {local_file} {user}@{host}:{remote_path}"


async def _run_pscp(host):
    """Асинхронная загрузка файлов через pscp"""
    files_to_upload = get_files_to_upload()

    if not files_to_upload:
        await log_message(f"{host}  Нет файлов для загрузки в директории {LOCAL_FILES}")
        return True

    success_count = 0
    total_files = len(files_to_upload)

    await log_message(f"{host}  Найдено файлов для загрузки: {total_files}")

    for local_file in files_to_upload:
        filename = os.path.basename(local_file)
        remote_path = f"{UPLOAD_FOLDER}/{filename}"

        cmd = PSCP_CMD.format(
            password=PASSWORD,
            local_file=local_file,
            user=USER,
            host=host,
            remote_path=remote_path,
        )

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
                stdout = stdout.decode().strip()
                stderr = stderr.decode().strip()

                if proc.returncode == 0:
                    await log_message(f"{host}  Файл {filename} успешно загружен")
                    success_count += 1
                else:
                    await log_message(
                        f"{host}  Ошибка загрузки {filename} (код {proc.returncode}): {stderr}"
                    )

            except asyncio.TimeoutError:
                await log_message(f"{host}  Таймаут загрузки файла {filename}")
                proc.kill()
                await proc.communicate()

        except Exception as e:
            await log_message(
                f"{host}  Критическая ошибка при загрузке {filename}: {str(e)}"
            )

    if success_count == total_files:
        await log_message(
            f"{host}  Все файлы ({success_count}/{total_files}) успешно загружены"
        )
        return True
    else:
        await log_message(f"{host}  Загружено файлов: {success_count}/{total_files}")
        return success_count > 0  # Возвращаем True если хотя бы один файл загружен
