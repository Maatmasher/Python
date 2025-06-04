import subprocess

result = subprocess.run(
    [
        "java",
        "-jar",
        "ConfiguratorCmdClient-1.5.1.jar",
        "-key1",
        "abc",
        "-key2",
        "qwerty",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

print("Return code:", result.returncode)
print("Output:", result.stdout)
print("Errors:", result.stderr)


# ===============================================================
def run_configurator(key1, key2, jar_path="ConfiguratorCmdClient-1.5.1.jar"):
    subprocess.run(["java", "-jar", jar_path, "-key1", key1, "-key2", key2], check=True)


# Использование
run_configurator("abc", "qwerty")

