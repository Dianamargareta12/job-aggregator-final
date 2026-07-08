def remove_duplicates(data):
    seen = set()
    result = []

    for item in data:
        link = item.get("link_lowongan")
        if link not in seen:
            seen.add(link)
            result.append(item)

    return result