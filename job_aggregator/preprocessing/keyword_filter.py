def filter_by_education(data, keyword):
    return [item for item in data if keyword.lower() in item.get("judul_posisi", "").lower()]