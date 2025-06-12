import subprocess
from typing import Dict, List, Optional, Union
import logging
from pathlib import Path


class ConfiguratorClient:
    def __init__(
        self, jar_path: str = "E:\\Distributives\\mook\\ConfiguratorCmdClient-1.5.1.jar"
    ):
        self.jar_path = Path(jar_path)
        if not self.jar_path.exists():
            raise FileNotFoundError(f"JAR file not found: {jar_path}")

    def execute_command(
        self,
        host: Optional[str] = None,
        centrum_host: Optional[str] = None,
        topology_point: Optional[str] = None,
        server: bool = False,
        version: Optional[str] = None,
        file_path: Optional[str] = None,
        server_version: Optional[str] = None,
        cash_version: Optional[str] = None,
        timeout: Optional[int] = None,
        no_backup: bool = False,
        auto_restart: bool = False,
        wait: bool = False,
        revert: bool = False,
        scheduled_cash_update: Optional[str] = None,
        scheduled_server_update: Optional[str] = None,
        cash_after_hours: Optional[int] = None,
        server_after_hours: Optional[int] = None,
        cancel_cash_update: bool = False,
        cancel_server_update: bool = False,
        shift_must_be_closed: bool = False,
        without_update: bool = False,
        remote_restart: bool = False,
        cancel_remote_restart: bool = False,
        all_nodes: bool = False,
    ) -> Dict[str, Union[int, str, List[Dict[str, str]]]]:
        """
        Execute ConfiguratorCmdClient command with specified parameters

        Args:
            host: IP address with SCM_SVC service (-h)
            centrum_host: Centrum IP address (-ch)
            topology_point: target topology point address (-tp)
            server: target point is server (-s)
            version: target version (-v)
            file_path: path to file with numbers of stores and cash (-f)
            server_version: target servers version for update (-sv)
            cash_version: target cash type and version for update (-cv)
            timeout: connection timeout in seconds (-t)
            no_backup: don't create database backups (-nb)
            auto_restart: auto restart POS when idle (-ar)
            wait: wait for update finish (-w)
            revert: allow downgrade (-r)
            scheduled_cash_update: scheduled CASH update date (-scu)
            scheduled_server_update: scheduled server update date (-ssu)
            cash_after_hours: start cash update after N hours (-ahc)
            server_after_hours: start server update after N hours (-ahs)
            cancel_cash_update: cancel recent cash update (-cu)
            cancel_server_update: cancel recent server update (-csu)
            shift_must_be_closed: shift must be closed for update (-smbc)
            without_update: download patch without apply (-wu)
            remote_restart: restart cash (-rr)
            cancel_remote_restart: cancel cash restart (-crr)
            all_nodes: get info on all nodes (--all)

        Returns:
            Dictionary with:
            - returncode: int
            - stdout: str
            - stderr: str
            - success: bool
            - parsed_output: List[Dict] (if output can be parsed)
        """
        # Build command
        cmd = ["java", "-jar", str(self.jar_path)]

        if host:
            cmd.extend(["-h", host])
        if centrum_host:
            cmd.extend(["-ch", centrum_host])
        if topology_point:
            cmd.extend(["-tp", topology_point])
        if server:
            cmd.append("-s")
        if version:
            cmd.extend(["-v", version])
        if file_path:
            cmd.extend(["-f", file_path])
        if server_version:
            cmd.extend(["-sv", server_version])
        if cash_version:
            cmd.extend(["-cv", cash_version])
        if timeout:
            cmd.extend(["-t", str(timeout)])
        if no_backup:
            cmd.append("-nb")
        if auto_restart:
            cmd.append("-ar")
        if wait:
            cmd.append("-w")
        if revert:
            cmd.append("-r")
        if scheduled_cash_update:
            cmd.extend(["-scu", scheduled_cash_update])
        if scheduled_server_update:
            cmd.extend(["-ssu", scheduled_server_update])
        if cash_after_hours is not None:
            cmd.extend(["-ahc", str(cash_after_hours)])
        if server_after_hours is not None:
            cmd.extend(["-ahs", str(server_after_hours)])
        if cancel_cash_update:
            cmd.append("-cu")
        if cancel_server_update:
            cmd.append("-csu")
        if shift_must_be_closed:
            cmd.append("-smbc")
        if without_update:
            cmd.append("-wu")
        if remote_restart:
            cmd.append("-rr")
        if cancel_remote_restart:
            cmd.append("-crr")
        if all_nodes:
            cmd.append("--all")

        try:
            result = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            output = {
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "success": result.returncode == 0,
                "command": " ".join(cmd),  # For debugging
            }

            # Try to parse output if successful
            if output["success"] and result.stdout.strip():
                try:
                    output["parsed_output"] = self._parse_output(result.stdout)
                except Exception as e:
                    logging.warning(f"Output parsing failed: {str(e)}")
                    output["parsed_output"] = None

            return output

        except subprocess.SubprocessError as e:
            logging.error(f"Command execution failed: {str(e)}")
            raise

    @staticmethod
    def _parse_output(output: str) -> List[Dict[str, str]]:
        """Parse the standard output from ConfiguratorCmdClient"""
        devices = []
        for line in output.strip().split("\n"):
            if not line:
                continue
            device = {}
            for pair in line.split(";"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    device[key.strip()] = (
                        value.strip() if value.strip().lower() != "null" else None
                    )
            if device:
                devices.append(device)
        return devices

    # Convenience methods for common operations
    def get_server_info(self, host: str) -> Dict:
        """Get information about server"""
        return self.execute_command(host=host, server=True)

    def get_all_nodes_info(self, centrum_host: str) -> Dict:
        """Get information about all nodes connected to Centrum"""
        return self.execute_command(centrum_host=centrum_host, all_nodes=True)

    def update_server(
        self, host: str, version: str, no_backup: bool = False, wait: bool = False
    ) -> Dict:
        """Update server to specified version"""
        return self.execute_command(
            host=host, server=True, version=version, no_backup=no_backup, wait=wait
        )

    def schedule_cash_update(
        self,
        host: str,
        topology_point: str,
        version: str,
        scheduled_date: str,
        after_hours: Optional[int] = None,
    ) -> Dict:
        """Schedule cash update for specific date/time"""
        return self.execute_command(
            host=host,
            topology_point=topology_point,
            version=version,
            scheduled_cash_update=scheduled_date,
            cash_after_hours=after_hours,
        )


# Примеры использования:

# Получение информации о сервере:
client = ConfiguratorClient()
result = client.get_server_info("10.100.105.9")
print(result["parsed_output"])

# Обновление сервера:
result = client.update_server(host="10.100.105.9", version="10.4.14.14", no_backup=True)

# Планирование обновления кассы:
result = client.schedule_cash_update(
    host="10.100.105.9",
    topology_point="TP001",
    version="10.4.11.13",
    scheduled_date="2025-06-15 02:00",
)

# Получение информации обо всех узлах:
result = client.get_all_nodes_info("10.100.105.9")
for device in result["parsed_output"]:
    print(f"{device['ip']}: {device['status']}")

# Сложный запрос с файлом конфигурации:
result = client.execute_command(
    centrum_host="10.100.105.9",
    file_path="E:\\Distributives\\mook\\server.txt",
    server_version="10.4.14.14",
    cash_version="RETAIL:10.4.11.13",
    all_nodes=True,
)
