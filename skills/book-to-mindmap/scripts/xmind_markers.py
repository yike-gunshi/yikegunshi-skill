"""XMind 内置标记 ID 清单（Xmind 26.02 应用包实测，197 个均有图标资源）

用途：生成 .xmind 前校验 markerId。写错不会报错，XMind 会原样保留但什么都不显示，
所以只能自己校验。

坑：
  - 下划线和连字符不通用。c_symbol_heart 有图标，symbol-heart 没有
  - c_simbol- 是产品里真实存在的拼写（少个 y），不要"修正"它
  - symbol-exclam 有效，symbol-exclamation 无效
  - 下面 UNSUPPORTED 里的 ID 在界面语言包中注册过但没有图标，一律不要用
"""

MARKERS = {
    "tag": "tag-red tag-orange tag-yellow tag-green tag-blue tag-dark-blue "
           "tag-dark-purple tag-grey",
    "priority": " ".join(f"priority-{i}" for i in range(1, 10)),
    "task": "task-start task-oct task-quarter task-3oct task-half task-5oct "
            "task-3quar task-7oct task-done task-pause",
    "flag": "flag-red flag-orange flag-yellow flag-green flag-blue flag-purple "
            "flag-gray flag-dark-blue flag-dark-green flag-dark-gray",
    "star": "star-red star-orange star-yellow star-green star-blue star-purple "
            "star-gray star-dark-blue star-dark-green star-dark-gray",
    "people": "people-red people-orange people-yellow people-green people-blue "
              "people-purple people-gray people-dark-blue people-dark-green "
              "people-dark-gray",
    "arrow": "arrow-up arrow-down arrow-left arrow-right arrow-up-left "
             "arrow-up-right arrow-down-left arrow-down-right arrow-left-right "
             "arrow-up-down arrow-refresh",
    "smiley": "smiley-smile smiley-laugh smiley-cry smiley-surprise smiley-boring "
              "smiley-angry smiley-embarrass smiley-think smiley-love smiley-sad "
              "smiley-cry-laugh smiley-adore smiley-devil smiley-upset",
    "academic": "symbol-plus symbol-minus symbol-divide symbol-equality "
                "symbol-not-equality symbol-question symbol-attention symbol-wrong "
                "symbol-right symbol-pause symbol-about symbol-code c_symbol_quote "
                "c_symbol_apostrophe",
    "social": "symbol-no-entry symbol-notice symbol-rss symbol-share symbol-comment "
              "symbol_forward c_symbol_heart c_symbol_broken_heart c_symbol_like "
              "c_symbol_dislike c_symbol_contact",
    "celebration": "celebration-100 celebration-birthday celebration-boom "
                   "celebration-cheers celebration-clap celebration-five "
                   "celebration-king celebration-kiss celebration-ribbon",
    "symbol": "symbol-plus symbol-minus symbol-question symbol-exclam symbol-info "
              "symbol-attention symbol-wrong symbol-right symbol-pause symbol-pin "
              "symbol-100 symbol-diamond symbol-entertainment symbol-idea "
              "symbol-lightning symbol-run symbol-unlock symbol-image "
              "c_simbol-plus c_simbol-minus c_simbol-question c_simbol-exclam "
              "c_simbol-info c_simbol-wrong c_simbol-right c_simbol-pause "
              "c_symbol_bar_chart c_symbol_pie_chart c_symbol_line_graph "
              "c_symbol_contact c_symbol_telephone c_symbol_pen c_symbol_money "
              "c_symbol_shopping_cart c_symbol_medals c_symbol_trophy "
              "c_symbol_music c_symbol_drink c_symbol_exercise c_symbol_flight "
              "c_symbol_hourglass c_symbol_lock c_symbol_thermometer",
    "month": " ".join(f"month-{m}" for m in
                      "jan feb mar apr may jun jul aug sep oct nov dec".split()),
    "week": " ".join(f"week-{d}" for d in "sun mon tue wed thu fri sat".split()),
    "half-star": "half-star-red half-star-yellow half-star-green half-star-blue "
                 "half-star-purple half-star-gray",
    "other": "other-calendar other-email other-phone other-phone2 other-fax "
             "other-people other-people2 other-clock other-coffee-cup other-question "
             "other-exclam other-lightbulb other-businesscard other-social other-chat "
             "other-note other-lock other-unlock other-yes other-no other-bomb",
}

VALID = {m for group in MARKERS.values() for m in group.split()}

# 语言包里注册过但没有图标，写了也不显示
UNSUPPORTED = {
    "tag-purple", "symbol-heart", "symbol-like", "symbol-dislike",
    "symbol-airplane", "symbol-exclamation", "symbol-hourglass", "symbol-music",
    "symbol-pen", "symbol-telephone",
}


def check(marker_id):
    """返回 None 表示可用，否则返回一句问题描述"""
    if marker_id in UNSUPPORTED:
        return f"{marker_id} 在 XMind 里没有图标，写了也不显示"
    if marker_id not in VALID:
        return f"{marker_id} 不是内置标记 ID，XMind 会原样保留但不显示任何图标"
    return None
