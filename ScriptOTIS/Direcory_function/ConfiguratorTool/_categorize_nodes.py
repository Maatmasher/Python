def _categorize_nodes(self):
    """Категоризация узлов по статусам"""
    self.work_tp = []
    self.error_tp = []
    self.update_tp = []
    self.ccm_tp = []
    self.unzip_tp = []
    self.no_update_needed_tp = []

    for node_id, node_data in self.node_result.items():
        status = (node_data.get("status") or "").upper()
        node_type = (node_data.get("type") or "").strip()
        tp = node_data.get("tp") or node_id
        if tp.split(".")[3] == "0":
            tp = tp.split(".")[2]
        else:
            tp = f"{tp.split('.')[2]}.{tp.split('.')[3]}"

        # Формируем строку для списка (tp-type)
        list_entry = f"{tp}"
        if node_type:
            list_entry += f"-{node_type}"

        # Категоризация по статусам
        if status == "IN_WORK":
            self.work_tp.append(list_entry)
        elif status in ("UPGRADE_ERROR_WITH_DOWNGRADE", "FAST_REVERT"):
            self.error_tp.append(list_entry)
        elif status in (
            "UPGRADE_PLANING",
            "UPGRADE_DOWNLOADING",
            "UPGRADE_WAIT_FOR_REBOOT",
            "CHECK_PERMISSIONS",
            "BACKUP",
            "APPLY_PATCH",
            "TEST_START",
        ):
            self.update_tp.append(list_entry)
        elif status == "CCM_UPDATE_RESTART":
            self.ccm_tp.append(list_entry)
        elif status == "UNZIP_FILES":
            self.unzip_tp.append(list_entry)
        elif status == "NO_UPDATE_NEEDED":
            self.no_update_needed_tp.append(list_entry)
