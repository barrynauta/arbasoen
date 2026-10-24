"""Fan chart edition: replaces the generated pedigree text with TikZ fan charts, five generations each.

Exec'd by run_local.py (--fan) after the notebook core, so it uses the core's names directly:
ahnen_map, tr, gedcom_config, pretty_date, pretty_place, is_approximate, IndexBuilder, LaTeX.
Each chart is rooted at an Ahnentafel number a and shows a and its ancestors up to a*16+15.
Every outer-ring person with known parents gets a follow-up chart. A person met again through
pedigree collapse gets no second chart; the wedge points to the chart already made.
"""
import re
from collections import deque

FAN_GENS = 5                                  # generations per chart, root included
RADII = [0, 1.6, 3.1, 4.6, 6.2, 8.2]          # cm, ring g runs from RADII[g] to RADII[g+1]
START_ANGLE, SPAN = 210, 240                  # fan runs clockwise from 210 to -30 degrees
MIN_FOLLOWUP = 4                              # a branch with fewer known ancestors gets no chart of its own;
                                              # they are listed under the chart it starts from
FONTS = [r"\small", r"\footnotesize", r"\scriptsize", r"\tiny", r"\tiny"]


def fan_year(*events) -> str:
    """First year found in the events (birth before baptism, death before burial), 'ca.' when approximate."""
    for e in events:
        if e is None or e.date is None:
            continue
        m = re.search(r"\d{4}", str(e.date))
        if m:
            return ("ca. " if is_approximate(e.date) else "") + m.group(0)
    return ""


def fan_name(person):
    """(given names, surname), LaTeX-escaped."""
    if isinstance(person.name, (tuple, list)):          # ged4py hands names over as (given, surname, suffix)
        given, surname = (list(person.name) + ["", ""])[:2]
        given, surname = given or "", surname or ""
    else:
        raw = str(person.name or "").strip()
        m = re.match(r"^(.*?)\s*/([^/]*)/\s*(.*)$", raw)
        given, surname = (m.group(1), m.group(2)) if m else (raw, "")
    esc = lambda s: s.strip().replace("_", r"\_").replace("&", r"\&")
    return esc(given) or "?", esc(surname)


def fan_label(person) -> str:
    given, surname = fan_name(person)
    born = fan_year(person.birth, person.baptism, person.christening)
    died = fan_year(person.death, person.burial)
    years = f"{born} - {died}" if (born or died) else ""
    label = given + (r"\\\textbf{" + surname + "}" if surname else "")
    return label + (r"\\{\color{black!60}" + years + "}" if years else "")


def fan_event(*events) -> str:
    for e in events:
        if e is not None and (e.date or e.place):
            place = pretty_place(e.place, 1) if e.place else ""
            return ", ".join(x for x in (pretty_date(e.date) if e.date else "", place) if x)
    return ""


def wedge(g, k, fill, label, link_text=""):
    """TikZ for position k in ring g (g >= 1) of the fan."""
    step = SPAN / 2 ** g
    a1 = START_ANGLE - k * step
    a2 = a1 - step
    mid = (a1 + a2) / 2
    r1, r2 = RADII[g], RADII[g + 1]
    rm = (r1 + r2) / 2
    out = (f"\\draw[fill={fill}, draw=white, line width=0.8pt] ({a1}:{r1}) arc ({a1}:{a2}:{r1}) "
           f"-- ({a2}:{r2}) arc ({a2}:{a1}:{r2}) -- cycle;\n")
    if g <= 2:   # inner rings: text along the arc
        width = min(2 * 3.1416 * rm * step / 360 * 0.85, 3.6)
        rot = mid - 90
    else:        # outer rings: text along the radius, never upside down
        width = (r2 - r1) * 0.92
        rot = mid if -90 <= mid <= 90 else mid + 180
    if label:
        out += (f"\\node[rotate={rot:.2f}, text width={width:.2f}cm, align=center, inner sep=0pt, "
                f"font={FONTS[g]}\\linespread{{0.85}}\\selectfont] at ({mid:.2f}:{rm:.2f}) {{{label}}};\n")
    if link_text:
        out += (f"\\node[rotate={rot if g > 2 else mid - 90:.2f}, font=\\tiny\\sffamily, text=kempen] "
                f"at ({mid:.2f}:{r2 + 0.3:.2f}) {{{link_text}}};\n")
    return out


def branch(ahnen_map, o):
    """Ahnentafel ids of all known ancestors of o, o itself excluded."""
    bits = o.bit_length()
    return sorted(x for x in ahnen_map if x > o and x >> (x.bit_length() - bits) == o)


def side_of(ahnen_map, aid) -> str:
    """Whose line an ahnen id comes through: the first given name of the father (2) or the mother (3)."""
    parent = 2 if aid >> (aid.bit_length() - 2) == 2 else 3
    return fan_name(ahnen_map[parent])[0].split()[0] if parent in ahnen_map else ""


def generate_fancharts(ahnen_map) -> str:
    charts = []                    # (chart number, root ahnen id, parent chart number)
    chart_of_ref = {}              # person ref -> chart number rooted at them
    extra = {}                     # chart number -> ancestors of small branches, listed under that chart
    beyond = {}                    # outer ahnen id -> number of ancestors listed instead of a chart
    first = {}                     # person ref -> (ahnen id, chart number) of the first appearance, in reading order
    shown_in = {}                  # ahnen id -> chart number where it is shown

    def see(aid, n):
        first.setdefault(ahnen_map[aid].ref, (aid, n))
        shown_in.setdefault(aid, n)

    def is_dup(aid):
        """Met before through pedigree collapse, under another ahnen id."""
        return first[ahnen_map[aid].ref][0] != aid

    def dup_top(aid):
        """A duplicate whose child in this line is not one: it gets the label, its ancestors stay blank."""
        return is_dup(aid) and not is_dup(aid // 2)

    queue = deque([(1, None)])
    while queue:                   # number the charts breadth first, so chart 2.. follow chart 1's outer ring
        a, parent = queue.popleft()
        n = len(charts) + 1
        charts.append((n, a, parent))
        chart_of_ref[ahnen_map[a].ref] = n
        see(a, n)
        for g in range(1, FAN_GENS):
            for k in range(2 ** g):
                if a * 2 ** g + k in ahnen_map:
                    see(a * 2 ** g + k, n)
        depth = 2 ** (FAN_GENS - 1)
        for k in range(depth):
            o = a * depth + k
            if o in ahnen_map and not is_dup(o) and (2 * o in ahnen_map or 2 * o + 1 in ahnen_map) \
                    and ahnen_map[o].ref not in chart_of_ref and all(ahnen_map[o].ref != ahnen_map[q[0]].ref for q in queue):
                anc = branch(ahnen_map, o)
                if len(anc) >= MIN_FOLLOWUP:
                    queue.append((o, n))
                else:
                    for x in anc:
                        see(x, n)
                    anc = [x for x in anc if not is_dup(x) or dup_top(x)]
                    extra.setdefault(n, []).extend(anc)
                    beyond[o] = len(anc)
    ref_chart = {ahnen_map[a].ref: n for n, a, _ in charts}

    def dup_note(aid):
        f_aid, f_n = first[ahnen_map[aid].ref]
        return f"dubbel, zie \\hyperlink{{fan{f_n}}}{{kaart {f_n}}}, nr.~\\hyperlink{{{f_aid}}}{{{f_aid}}}"

    targets = set()
    out = "\\chapter{Kwartierstaat in waaiers}\n"
    out += ("Elke waaier toont vijf generaties: in het midden de persoon met wie de kaart begint, "
            "daarrond de ouders, grootouders, overgrootouders en betovergrootouders. "
            "Vaderszijde staat links, moederszijde rechts. Een pijltje met een nummer aan de buitenrand "
            "verwijst naar de kaart waar die lijn verder gaat. Een plusteken met een getal betekent dat "
            "er nog zoveel voorouders bekend zijn, te weinig voor een eigen kaart: zij staan in de lijst "
            "onder de waaier. Een grijs vak met \\textit{dubbel} is een voorouder die al op een eerdere "
            "kaart staat, langs een andere lijn. Het nummer zegt op welke kaart. Wie daarboven staat, "
            "wordt niet herhaald: die vakken blijven grijs. Onder elke waaier staan de gegevens "
            "per persoon, met het kwartiernummer.\n\n")

    # the couples (or single persons) met more than once, for the Verre familie section
    groups = {}                    # ref of the first appearance -> ahnen ids of the later ones
    for aid in sorted(shown_in):
        if aid > 1 and dup_top(aid) and not (aid % 2 == 1 and aid - 1 in shown_in and dup_top(aid - 1)):
            groups.setdefault(ahnen_map[aid].ref, []).append(aid)
    if groups:
        out += "\\section*{Dubbele voorouders}\\hypertarget{dubbel}{}\n"
        out += ("Deze voorouders staan meer dan een keer in de waaiers. Waar een man en een vrouw "
                "allebei dubbel zijn, staat alleen het echtpaar. Zie ook \\textit{Verre familie} vooraan.\n\n")
        out += "{\\small\\noindent\\begin{tabularx}{\\textwidth}{@{}>{\\raggedright\\arraybackslash}X>{\\raggedright\\arraybackslash}p{4.2cm}>{\\raggedright\\arraybackslash}p{4.2cm}@{}}\n"
        out += "\\textbf{voorouder} & \\textbf{eerste keer} & \\textbf{ook}\\\\\\hline\n"
        for ref, later in sorted(groups.items(), key=lambda kv: first[kv[0]][0]):
            f_aid, f_n = first[ref]
            given, surname = fan_name(ahnen_map[f_aid])
            who = f"{given} \\textbf{{{surname}}}"
            if f_aid % 2 == 0 and f_aid + 1 in shown_in and \
                    all(x + 1 in shown_in and dup_top(x + 1) for x in later):
                g2, s2 = fan_name(ahnen_map[f_aid + 1])
                who += f" en {g2} \\textbf{{{s2}}}"
            where = lambda x, m: f"\\hyperlink{{fan{m}}}{{kaart {m}}}, nr.~{x} ({side_of(ahnen_map, x)})"
            again = "; ".join(where(x, shown_in[x]) for x in later)
            out += f"{who} & {where(f_aid, f_n)} & {again}\\\\\n"
        out += "\\end{tabularx}}\n\n"

    for n, a, parent in charts:
        root = ahnen_map[a]
        given, surname = fan_name(root)
        out += "\\clearpage\n"
        out += f"\\section{{Kaart {n}: {given} {surname}}}\\hypertarget{{fan{n}}}{{}}\n"
        gen = a.bit_length()       # Ester (1) is generation 1, her parents 2, and so on
        line = f"Generatie {gen} tot en met {gen + FAN_GENS - 1}."
        if parent:
            line += f" Vervolg van \\hyperlink{{fan{parent}}}{{kaart {parent}}}, kwartier {a}."
        out += f"{{\\small\\color{{heide}}{line}}}\n\n"
        out += "\\noindent\\makebox[\\textwidth][c]{\\begin{tikzpicture}[scale=" + ("0.82" if n in extra else "0.9") + ", every node/.style={transform shape}]\n"
        out += f"\\draw[fill=zand, draw=white] (0,0) circle ({RADII[1]});\n"
        out += (f"\\node[text width=2.8cm, align=center, font=\\small\\linespread{{0.85}}\\selectfont] "
                f"at (0,0.15) {{{fan_label(root)}}};\n")
        rows = [(a, root)]
        for g in range(1, FAN_GENS):
            for k in range(2 ** g):
                aid = a * 2 ** g + k
                side = "kempen" if k < 2 ** (g - 1) else "heide"
                p = ahnen_map.get(aid)
                if p is None:
                    out += wedge(g, k, "black!4", "")
                    continue
                if is_dup(aid):
                    if dup_top(aid):
                        rows.append((aid, p))
                        gv, sn = fan_name(p)
                        f_n = first[p.ref][1]
                        label = gv + (r"\\\textbf{" + sn + "}" if sn else "") + \
                            f"\\\\{{\\color{{black!60}}dubbel, \\hyperlink{{fan{f_n}}}{{kaart {f_n}}}}}"
                        out += wedge(g, k, "black!12", label)
                    else:
                        out += wedge(g, k, "black!12", "")
                    continue
                rows.append((aid, p))
                link = ""
                if p.ref in ref_chart and ref_chart[p.ref] != n:
                    m = ref_chart[p.ref]
                    link = f"\\hyperlink{{fan{m}}}{{$\\rightarrow$\\,{m}}}"
                elif aid in beyond:
                    link = f"+{beyond[aid]}"
                out += wedge(g, k, f"{side}!{8 + 4 * g}", fan_label(p), link)
        out += "\\end{tikzpicture}}\n\n\\vspace{0.2cm}\n"

        # the data per person, also the anchor for links from the other chapters
        out += "{\\scriptsize\\renewcommand{\\arraystretch}{1.0}\n"
        out += "\\noindent\\begin{tabularx}{\\textwidth}{@{}r>{\\raggedright\\arraybackslash}p{5.4cm}>{\\raggedright\\arraybackslash}X>{\\raggedright\\arraybackslash}X@{}}\n"
        out += "\\textbf{nr} & \\textbf{naam} & \\textbf{geboren / gedoopt} & \\textbf{overleden / begraven}\\\\\\hline\n"
        for aid, p in rows:
            given, surname = fan_name(p)
            anchor = ""
            if aid not in targets:
                targets.add(aid)
                anchor = f"\\hypertarget{{{aid}}}{{}}"
            name = f"{given} \\textbf{{{surname}}}"
            if is_dup(aid):
                out += f"{anchor}{aid} & {name} & \\multicolumn{{2}}{{l}}{{\\textit{{{dup_note(aid)}}}}}\\\\\n"
                continue
            m = ref_chart.get(p.ref)
            if m and m != n:
                name += f" \\hyperlink{{fan{m}}}{{(kaart {m})}}"
            born = fan_event(p.birth, p.baptism, p.christening)
            died = fan_event(p.death, p.burial)
            out += f"{anchor}{aid} & {name} & {born} & {died}\\\\\n"
        out += "\\end{tabularx}}\n"
        if n in extra:   # short branches: one running paragraph keeps the chart on one page
            items = []
            for aid in extra[n]:
                p = ahnen_map[aid]
                given, surname = fan_name(p)
                anchor = ""
                if aid not in targets:
                    targets.add(aid)
                    anchor = f"\\hypertarget{{{aid}}}{{}}"
                if is_dup(aid):
                    items.append(f"{anchor}{aid}~{given} \\textbf{{{surname}}} ({dup_note(aid)})")
                    continue
                born = fan_year(p.birth, p.baptism, p.christening)
                died = fan_year(p.death, p.burial)
                years = f" ({born} - {died})" if (born or died) else ""
                items.append(f"{anchor}{aid}~{given} \\textbf{{{surname}}}{years}")
            out += ("\n\\vspace{0.15cm}{\\scriptsize\\noindent\\textit{Verder terug, te weinig voor een eigen kaart:} "
                    + "; ".join(items) + ".\\par}\n")

    # every ahnen id the other chapters may link to gets an anchor, also those not shown
    # (ancestors of a duplicate): they land at the end of the chapter
    for aid, p in sorted(ahnen_map.items()):
        if aid not in targets and p.ref in ref_chart:
            out += f"\\hypertarget{{{aid}}}{{}}"
            targets.add(aid)
    dups = sum(1 for aid in shown_in if aid > 1 and dup_top(aid))
    print(f"{ok}fan charts: {len(charts)} charts, {len(targets)} anchors, {dups} duplicates marked, {len(groups)} groups")
    return out
