import json
from pathlib import Path

PROM = {"type": "prometheus", "uid": "prometheus"}
CH = {"type": "grafana-clickhouse-datasource", "uid": "clickhouse-dw"}

UP_DOWN = [{"type": "value", "options": {
    "1": {"text": "UP", "color": "green", "index": 0},
    "0": {"text": "DOWN", "color": "red", "index": 1}}}]

PLATFORM_LINKS = [{"title": "All dashboards", "type": "dashboards", "tags": ["platform"], "asDropdown": True,
                   "includeVars": False, "keepTime": True, "targetBlank": False, "icon": "external link"}]


def prom(expr, legend=None, instant=False, ref="A", fmt=None):
    t = {"datasource": PROM, "expr": expr, "refId": ref, "editorMode": "code",
         "range": not instant, "instant": instant}
    if legend is not None:
        t["legendFormat"] = legend
    if fmt:
        t["format"] = fmt
    return t


def sql(query, timeseries=False, ref="A"):
    return {"datasource": CH, "editorType": "sql", "format": 0 if timeseries else 1,
            "queryType": "timeseries" if timeseries else "table", "rawSql": query, "refId": ref}


def steps(*pairs):
    out = [{"color": pairs[0], "value": None}]
    for i in range(1, len(pairs), 2):
        out.append({"color": pairs[i + 1], "value": pairs[i]})
    return {"mode": "absolute", "steps": out}


def fixed(color):
    return {"mode": "fixed", "fixedColor": color}


def _panel(kind, title, targets, options, defaults=None, overrides=None, description=None, transformations=None,
           datasource=None):
    if not isinstance(targets, list):
        targets = [targets]
    p = {"type": kind, "title": title, "datasource": datasource or targets[0]["datasource"], "targets": targets,
         "fieldConfig": {"defaults": defaults or {}, "overrides": overrides or []}, "options": options}
    if description:
        p["description"] = description
    if transformations:
        p["transformations"] = transformations
    return p


def _defaults(unit=None, decimals=None, minimum=None, maximum=None, color=None, thresholds=None, mappings=None,
              no_value=None, custom=None):
    d = {}
    for key, value in (("unit", unit), ("decimals", decimals), ("min", minimum), ("max", maximum),
                       ("color", color), ("thresholds", thresholds), ("mappings", mappings),
                       ("noValue", no_value), ("custom", custom)):
        if value is not None:
            d[key] = value
    return d


def _reduce(values=False, calcs=("lastNotNull",)):
    return {"calcs": list(calcs), "fields": "", "values": values}


def override(name, **props):
    return {"matcher": {"id": "byName", "options": name},
            "properties": [{"id": k.replace("_", "."), "value": v} for k, v in props.items()]}


def override_regex(regex, **props):
    return {"matcher": {"id": "byRegexp", "options": regex},
            "properties": [{"id": k.replace("_", "."), "value": v} for k, v in props.items()]}


def stat(title, targets, unit=None, color=None, thresholds=None, mappings=None, decimals=None, graph=False,
         text_mode="auto", color_mode="background", no_value=None, description=None, values=False,
         orientation="auto", overrides=None, calcs=("lastNotNull",)):
    if color and not thresholds:
        color_cfg = fixed(color)
    else:
        color_cfg = {"mode": "thresholds"}
    return _panel("stat", title, targets, {
        "reduceOptions": _reduce(values, calcs), "colorMode": color_mode, "graphMode": "area" if graph else "none",
        "textMode": text_mode, "justifyMode": "center", "orientation": orientation, "wideLayout": True,
        "showPercentChange": False},
        _defaults(unit, decimals, color=color_cfg, thresholds=thresholds or steps("green"), mappings=mappings,
                  no_value=no_value), overrides=overrides, description=description)


def gauge(title, targets, unit="percent", minimum=0, maximum=100, thresholds=None, decimals=1, scheme=None,
          description=None, no_value=None):
    color = {"mode": scheme} if scheme else {"mode": "thresholds"}
    return _panel("gauge", title, targets, {
        "reduceOptions": _reduce(), "showThresholdLabels": False, "showThresholdMarkers": True, "sizing": "auto",
        "minVizWidth": 75, "minVizHeight": 75, "orientation": "auto"},
        _defaults(unit, decimals, minimum, maximum, color, thresholds or steps("green", 70, "orange", 85, "red"),
                  no_value=no_value), description=description)


def bargauge(title, targets, unit=None, mode="gradient", minimum=0, maximum=None, thresholds=None, scheme=None,
             decimals=None, values=False, description=None, overrides=None, no_value=None, orientation="horizontal",
             transformations=None):
    color = {"mode": scheme} if scheme else {"mode": "thresholds"}
    return _panel("bargauge", title, targets, {
        "reduceOptions": _reduce(values), "displayMode": mode, "orientation": orientation, "valueMode": "color",
        "namePlacement": "auto", "showUnfilled": True, "sizing": "auto", "minVizHeight": 16, "minVizWidth": 8,
        "maxVizHeight": 300},
        _defaults(unit, decimals, minimum, maximum, color, thresholds or steps("green"), no_value=no_value),
        overrides=overrides, description=description, transformations=transformations)


def timeseries(title, targets, unit=None, stack=False, fill=25, draw="line", decimals=None, minimum=None,
               maximum=None, scheme="palette-classic", gradient="opacity", overrides=None, description=None,
               no_value=None, legend_calcs=("mean", "max", "lastNotNull"), thresholds=None, threshold_style=None):
    custom = {"drawStyle": draw, "lineWidth": 2 if draw == "line" else 1, "fillOpacity": fill,
              "gradientMode": gradient, "lineInterpolation": "smooth", "showPoints": "never", "spanNulls": True,
              "axisSoftMin": 0, "barAlignment": 0,
              "stacking": {"mode": "normal" if stack else "none", "group": "A"}}
    if threshold_style:
        custom["thresholdsStyle"] = {"mode": threshold_style}
    return _panel("timeseries", title, targets, {
        "legend": {"showLegend": True, "displayMode": "table" if legend_calcs else "list", "placement": "bottom",
                   "calcs": list(legend_calcs or [])},
        "tooltip": {"mode": "multi", "sort": "desc"}},
        _defaults(unit, decimals, minimum, maximum, {"mode": scheme}, thresholds, no_value=no_value, custom=custom),
        overrides=overrides, description=description)


def state_timeline(title, targets, mappings, description=None, row_height=0.85):
    return _panel("state-timeline", title, targets, {
        "showValue": "never", "mergeValues": True, "rowHeight": row_height, "alignValue": "center",
        "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"},
        "tooltip": {"mode": "single", "sort": "none"}},
        _defaults(color={"mode": "thresholds"}, thresholds=steps("red", 1, "green"), mappings=mappings,
                  custom={"fillOpacity": 85, "lineWidth": 0}), description=description)


def pie(title, targets, unit="short", donut=True, values=False, overrides=None, description=None,
        scheme="palette-classic", legend_values=("value", "percent")):
    return _panel("piechart", title, targets, {
        "pieType": "donut" if donut else "pie", "reduceOptions": _reduce(values),
        "displayLabels": ["percent"],
        "legend": {"showLegend": True, "displayMode": "table", "placement": "right", "values": list(legend_values)},
        "tooltip": {"mode": "single", "sort": "none"}},
        _defaults(unit, color={"mode": scheme}), overrides=overrides, description=description)


def barchart(title, targets, unit=None, stack=False, horizontal=False, scheme="palette-classic", decimals=None,
             overrides=None, transformations=None, description=None, show_value="auto", rotate=0,
             color_by_field=None):
    options = {"orientation": "horizontal" if horizontal else "vertical", "showValue": show_value,
               "stacking": "normal" if stack else "none", "groupWidth": 0.75, "barWidth": 0.9, "barRadius": 0.1,
               "xTickLabelRotation": rotate, "xTickLabelSpacing": 0,
               "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"},
               "tooltip": {"mode": "multi", "sort": "desc"}}
    if color_by_field:
        options["colorByField"] = color_by_field
    overrides = [{"matcher": {"id": "byRegexp", "options": "/^(year|sat)/"},
                  "properties": [{"id": "unit", "value": "string"}]}] + list(overrides or [])
    return _panel("barchart", title, targets, options,
                  _defaults(unit, decimals, color={"mode": scheme},
                            custom={"fillOpacity": 85, "gradientMode": "hue", "lineWidth": 1, "axisSoftMin": 0}),
                  overrides=overrides, transformations=transformations, description=description)


def table(title, targets, unit=None, overrides=None, transformations=None, description=None, no_value=None,
          cell="auto", mappings=None, thresholds=None, scheme=None, sort_by=None):
    color = {"mode": scheme} if scheme else {"mode": "thresholds"}
    options = {"showHeader": True, "cellHeight": "sm", "footer": {"show": False, "reducer": ["sum"], "fields": ""}}
    if sort_by:
        options["sortBy"] = [{"displayName": sort_by[0], "desc": sort_by[1]}]
    return _panel("table", title, targets, options,
                  _defaults(unit, color=color, thresholds=thresholds or steps("text"), mappings=mappings,
                            no_value=no_value, custom={"align": "auto", "cellOptions": {"type": cell},
                                                       "filterable": False}),
                  overrides=overrides, transformations=transformations, description=description)


def text(title, content, mode="markdown"):
    return {"type": "text", "title": title, "options": {"mode": mode, "content": content}}


class Layout:
    def __init__(self):
        self.panels, self.x, self.y, self.row_h, self.next_id = [], 0, 0, 0, 1

    def _place(self, panel, w, h):
        if self.x + w > 24:
            self.x, self.y, self.row_h = 0, self.y + self.row_h, 0
        panel["id"] = self.next_id
        panel["gridPos"] = {"x": self.x, "y": self.y, "w": w, "h": h}
        self.next_id += 1
        self.x += w
        self.row_h = max(self.row_h, h)
        self.panels.append(panel)
        return panel

    def add(self, panel, w, h):
        return self._place(panel, w, h)

    def row(self, title):
        if self.x:
            self.x, self.y, self.row_h = 0, self.y + self.row_h, 0
        self._place({"type": "row", "title": title, "collapsed": False, "panels": []}, 24, 1)
        self.x, self.y, self.row_h = 0, self.y + 1, 0


def dashboard(uid, title, layout, refresh="30s", time_from="now-1h", tags=(), description=None, variables=None):
    d = {"uid": uid, "title": title, "tags": ["platform", *(t for t in tags if t != "platform")], "timezone": "browser", "schemaVersion": 39,
         "version": 1, "editable": False, "graphTooltip": 1, "refresh": refresh,
         "time": {"from": time_from, "to": "now"}, "panels": layout.panels,
         "templating": {"list": variables or []}, "annotations": {"list": []}, "links": PLATFORM_LINKS}
    if description:
        d["description"] = description
    return d


def prom_variable(name, label, query, multi=True):
    return {"name": name, "label": label, "type": "query", "datasource": PROM,
            "query": {"query": query, "refId": "PrometheusVariableQueryEditor-VariableQuery", "qryType": 1},
            "definition": query, "refresh": 2, "sort": 1, "multi": multi, "includeAll": multi,
            "current": {"selected": True, "text": ["All"], "value": ["$__all"]} if multi else {},
            "hide": 0, "options": []}


def write(directory, name, data):
    path = Path(directory) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return path
