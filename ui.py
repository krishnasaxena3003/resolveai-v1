"""Visual layer: the approved ResolveAI editorial design (cream paper, serif headlines, teal accent)."""
import html
import streamlit as st

h = html.escape
CSS = """
:root{--bg:#FFFCF8;--card:#fff;--sunk:#F5EFE6;--ink:#1E1A17;--mute:#6F675F;--line:#E6DFD4;--accent:#2F5D50;--clay:#B5532F;--clay-bg:#F7E4DC;--ochre:#9A6B12;--ochre-bg:#F6EBCF;--ok-bg:#E1EEE8;--serif:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;--sans:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;--pad:clamp(18px,4vw,48px)}
header[data-testid="stHeader"],#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"]{display:none!important}
html,body,.stApp,[data-testid="stAppViewContainer"]{background:var(--bg)!important;color:var(--ink);font:400 16px/1.6 var(--sans);font-synthesis:none;text-rendering:optimizeLegibility}
[data-testid="stAppViewContainer"]{position:relative;background:transparent!important}
.stApp::before{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;background:radial-gradient(ellipse at 8% 18%,rgba(47,93,80,.10),transparent 34%),radial-gradient(ellipse at 92% 58%,rgba(181,83,47,.07),transparent 32%),linear-gradient(180deg,#FFFCF8 0%,#F8F4EC 100%)}
.stApp>header,.stApp [data-testid="stAppViewContainer"]>section{position:relative;z-index:1}
[data-testid="stAppViewContainer"]{overflow-x:hidden}
.block-container{max-width:1180px!important;padding:0 var(--pad) 150px!important}
.stMarkdown p,.stMarkdown li,.stMarkdown span{font-family:var(--sans)}
.d1,.d2,.d3{font-family:var(--sans);font-weight:600;letter-spacing:-.025em;line-height:1.08;color:var(--ink)}
.d1{font-size:clamp(46px,7.4vw,104px)}.d1 em{font-style:italic;color:var(--accent)}.d2{font-size:clamp(34px,5vw,60px);max-width:16ch}.d3{font-size:25px}
.pgh{font-family:var(--sans);font-weight:600;letter-spacing:-.025em;line-height:1.05;font-size:clamp(38px,5.5vw,68px);margin:10px 0 14px}
.eyebrow{font:500 11.5px var(--sans);letter-spacing:.16em;text-transform:uppercase;color:var(--mute)}
.lead{color:var(--mute);max-width:56ch;margin:0 0 30px}
/* Use crisp OS fonts; avoid remote webfont swaps that can blur or delay text. */
.stApp,.stApp *{font-family:var(--sans)}
.stApp :is(.d1,.d2,.d3,.pgh,.logo,.big,.fbig,.idbig,.id,.n,.stats b,.idx b,.wf td:first-child,.logo i,.d1 em,.big em,.d2 em){font-family:var(--serif)!important}
.stApp :is(.mono,code,pre){font-family:ui-monospace,Consolas,monospace!important}
.stApp [data-testid="stIconMaterial"],.stApp [class*="material-symbols"]{font-family:"Material Symbols Rounded"!important}
/* nav */
.st-key-nav{position:sticky;top:0;z-index:50;background:var(--bg);box-shadow:0 0 0 100vmax var(--bg);clip-path:inset(0 -100vmax)}
.st-key-nav::after{content:"";position:absolute;bottom:0;left:50%;width:100vw;margin-left:-50vw;border-bottom:1px solid var(--line)}
.logo{font:400 24px var(--serif);letter-spacing:-.03em;color:var(--ink);line-height:64px}.logo i{font-style:italic;color:var(--accent)}
.st-key-navradio{padding-top:16px}.st-key-navradio [data-testid="stVerticalBlock"]{align-items:flex-end}.st-key-navradio [data-testid="stElementContainer"]{display:flex;justify-content:flex-end;width:100%}.st-key-navradio [data-testid="stRadio"]{width:max-content}.st-key-navradio [role="radiogroup"]{gap:clamp(12px,3vw,32px);flex-wrap:nowrap;justify-content:flex-end}
.st-key-navradio [data-testid="stRadioOption"]{margin:0;padding:4px 0;border-bottom:1px solid transparent;cursor:pointer;background:none}
.st-key-navradio [data-testid="stRadioOption"]>div>div:first-child{display:none}
.st-key-navradio [data-testid="stRadioOption"] p{font:500 12px var(--sans)!important;letter-spacing:.12em;text-transform:uppercase;color:var(--mute)!important;margin:0}
.st-key-navradio [data-testid="stRadioOption"][data-selected="true"]{border-bottom-color:var(--ink)}.st-key-navradio [data-testid="stRadioOption"][data-selected="true"] p{color:var(--ink)!important}
/* buttons */
button[data-testid^="stBaseButton-primary"],button[data-testid^="stBaseButton-secondary"]{border-radius:999px;padding:8px 24px;font:500 14px var(--sans);min-height:0;box-shadow:none}
button[data-testid^="stBaseButton-primary"]{background:var(--accent);border:1px solid var(--accent);color:#FFFCF8}
button[data-testid^="stBaseButton-primary"] p{color:#FFFCF8!important}
button[data-testid^="stBaseButton-secondary"]{background:transparent;border:1px solid var(--ink);color:var(--ink)}
button[data-testid^="stBaseButton-primary"]:hover{background:#244A40;border-color:#244A40}button[data-testid^="stBaseButton-secondary"]:hover{background:var(--sunk);border-color:var(--ink);color:var(--ink)}
.st-key-cta{position:fixed;left:50%;transform:translateX(-50%);bottom:18px;z-index:60;width:auto!important}
.st-key-cta button{box-shadow:0 10px 30px -10px rgba(0,0,0,.4);padding:12px 28px}
/* fields */
[data-testid="stWidgetLabel"] p{font:500 11.5px var(--sans)!important;letter-spacing:.14em;text-transform:uppercase;color:var(--mute)!important}
div[data-baseweb="input"],div[data-baseweb="textarea"],div[data-baseweb="select"]>div{background:var(--card)!important;border:1px solid var(--line)!important;border-radius:6px!important}
div[data-baseweb="input"] input,div[data-baseweb="textarea"] textarea{background:transparent!important;color:var(--ink)}
[data-testid="stTextInputRootElement"],[data-testid="stTextAreaRootElement"],[data-testid="stSelectbox"] [data-baseweb="select"],[data-testid="stSelectbox"] [data-baseweb="select"]>div{background:var(--card)!important;box-shadow:none!important}
[data-testid="stSelectbox"] [data-baseweb="select"]>div{border:1px solid var(--line)!important;border-radius:6px!important}
[data-testid="stAlertContainer"]{background:var(--sunk)!important;color:var(--ink)!important;border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:6px}
[data-testid="stAlertContainer"] *{color:var(--ink)!important}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]){background:var(--ochre-bg)!important;border-left-color:var(--ochre)}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]){background:var(--clay-bg)!important;border-left-color:var(--clay)}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]){background:var(--ok-bg)!important}
[data-testid="stSelectbox"] [role="group"]{background:var(--card)!important;border:1px solid var(--line)!important;border-radius:6px!important;box-shadow:none!important}
[role="tablist"]{gap:22px;border-bottom:1px solid var(--line)}[data-testid="stTab"]{padding:8px 0;background:transparent}
[data-testid="stTab"] p{font:500 12px var(--sans)!important;letter-spacing:.12em;text-transform:uppercase;color:var(--mute)!important}
[data-testid="stTab"][data-selected="true"] p{color:var(--ink)!important}[data-testid="stTab"] .react-aria-SelectionIndicator{background:var(--ink)!important;height:1px!important}
[data-testid="stForm"]{border:0!important;padding:0!important}
/* panels (keyed containers) */
[class*="st-key-panel"]{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:26px}
[class*="st-key-panel"] .pgh,[class*="st-key-panel"] .d3{font-size:26px;margin:0 0 12px}
.st-key-okpanel{background:var(--ok-bg);border:1px solid var(--accent);border-radius:6px;padding:24px}
/* components */
.out dd a{color:inherit!important;text-decoration:none!important;pointer-events:none}
.t td:last-child{white-space:nowrap}.st-key-okpanel .tag.g{background:#fff}
.stMarkdown table.wf th,.stMarkdown table.wf td,.stMarkdown table.t th,.stMarkdown table.t td{border-left:0!important;border-right:0!important;border-top:0!important}
.stMarkdown table.wf td,.stMarkdown table.t td,.stMarkdown table.t th{border-bottom:1px solid var(--line)!important}.stMarkdown table.wf th{border-bottom:1px solid var(--ink)!important}
.stApp .big{font-size:clamp(26px,3.6vw,46px)!important;line-height:1.22}
.sec{position:relative;padding:84px 0}.sec::before{content:"";position:absolute;top:0;left:50%;width:100vw;margin-left:-50vw;border-top:1px solid var(--line)}
.phil{isolation:isolate}.phil::after{content:"";position:absolute;top:0;bottom:0;left:50%;width:100vw;margin-left:-50vw;background:var(--sunk);z-index:-1}
.hero-wrap{padding:clamp(40px,8vw,96px) 0 6px}.st-key-herobtns{margin-top:22px}.slip .out{grid-template-columns:104px 1fr;font-size:14px}.st-key-herobtns [data-testid="stHorizontalBlock"]{gap:12px;flex-wrap:nowrap}.st-key-herobtns [data-testid="stColumn"]{width:auto!important;flex:0 0 auto!important;min-width:0}.hero-p{font-size:19px;color:var(--mute);max-width:46ch;margin:26px 0 0}.hero-wrap .eyebrow,.slip .eyebrow{font-size:19px}
.slip{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:26px;box-shadow:0 1px 0 var(--line),0 24px 40px -28px rgba(30,26,23,.35);transform:rotate(1.2deg);margin-top:clamp(20px,6vw,90px)}
.slip .id,.idbig{font:600 34px var(--serif);margin:6px 0 14px;letter-spacing:-.02em}.idbig{font-size:40px;margin:2px 0 8px}
.out{display:grid;grid-template-columns:104px 1fr;gap:10px 14px;margin:0;font-size:14.5px}.out dt{color:var(--mute)}.out dd{margin:0;font-weight:500}
.why{display:grid;grid-template-columns:repeat(4,1fr);gap:36px;margin-top:48px}.why .n{font:600 20px var(--serif);color:var(--accent)}.why .d3{margin:10px 0}.why p{margin:0;color:var(--mute);font-size:15px}
.big{font:600 clamp(26px,3.6vw,46px)/1.22 var(--serif);letter-spacing:-.02em;max-width:26ch;margin:20px 0 0}.big em{font-style:italic;color:var(--accent)}
table.wf{width:100%;border-collapse:collapse;margin-top:40px}.wf th{font:500 11.5px var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--mute);text-align:left;padding:10px 12px 10px 0;border-bottom:1px solid var(--ink)}
.wf td{padding:16px 12px 16px 0;border-bottom:1px solid var(--line);vertical-align:top;font-size:15px}.wf td:first-child{font:600 22px var(--serif);white-space:nowrap}.wf td:nth-child(3){color:var(--mute)}
.fbig{font:600 clamp(30px,5vw,56px) var(--serif);letter-spacing:-.03em;margin-bottom:30px}.idx{display:grid;grid-template-columns:48px 1fr;gap:10px 8px;font-size:14.5px;max-width:640px}.idx b{font:600 20px var(--serif)}.idx span{color:var(--mute)}
.tag{display:inline-block;font:500 11px var(--sans);letter-spacing:.1em;text-transform:uppercase;padding:3px 9px;border-radius:999px;border:1px solid var(--line);color:var(--mute);white-space:nowrap;margin:0 6px 6px 0}
.tag.g{background:var(--ok-bg);border-color:transparent;color:var(--accent)}.tag.o{background:var(--ochre-bg);border-color:transparent;color:var(--ochre)}.tag.c{background:var(--clay-bg);border-color:transparent;color:var(--clay)}
.pd{display:inline-flex;align-items:center;gap:7px;font-weight:500}.pd::before{content:"";width:9px;height:9px;border-radius:50%;background:var(--mute)}.pd.High::before{background:var(--clay)}.pd.Medium::before{background:var(--ochre)}.pd.Low::before{background:transparent;border:1.5px solid var(--mute)}
.st{display:inline-flex;align-items:center;gap:7px}.st::before{content:"";width:11px;height:11px;border-radius:50%;border:1.5px solid var(--accent);background:conic-gradient(var(--accent) var(--p,0%),transparent 0)}.st.Open{--p:0%}.st.InProgress{--p:50%}.st.Resolved{--p:100%}
.dupc{border:1px solid var(--ochre);background:var(--ochre-bg);border-radius:6px;padding:16px;margin:14px 0 8px}.dupc p{margin:6px 0}.dupc small{color:var(--mute)}
.note{color:var(--mute);font-size:13.5px;margin:12px 0 0}.ph{color:var(--mute);min-height:150px;display:grid;place-items:center;text-align:center}
.demo{background:var(--ochre-bg);color:var(--ochre);font:500 12.5px var(--sans);padding:8px 14px;border-radius:6px;margin:10px 0 0}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:6px;overflow:hidden;margin:26px 0}.stats div{background:var(--card);padding:18px 22px}.stats b{display:block;font:600 44px/1 var(--serif)}.stats span{color:var(--mute);font-size:13px}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--card);margin:6px 0 24px}table.t{border-collapse:collapse;width:100%;font-size:14px;min-width:680px}
.t th{font:500 11px var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--mute);text-align:left;padding:12px;border-bottom:1px solid var(--line)}.t td{padding:12px;border-bottom:1px solid var(--line);vertical-align:top}.t .mono{font:500 12.5px ui-monospace,Consolas,monospace;white-space:nowrap}
@media (max-width:960px){.why{grid-template-columns:1fr 1fr}.stats{grid-template-columns:1fr 1fr}.slip{transform:none;margin-top:10px}.wf .hm{display:none}}
@media (max-width:700px){.st-key-navradio{padding-top:0;padding-bottom:10px}.st-key-navradio [role="radiogroup"]{flex-wrap:nowrap;overflow-x:auto;justify-content:flex-start;gap:20px;scrollbar-width:none}
.st-key-navradio [data-testid="stRadioOption"]{flex:0 0 auto}.st-key-navradio [data-testid="stRadioOption"] p{white-space:nowrap;font-size:11px!important;letter-spacing:.08em}
.st-key-nav [data-testid="stVerticalBlock"]{gap:0}.logo{line-height:52px}
.st-key-navradio [data-testid="stVerticalBlock"]{align-items:stretch}.st-key-navradio [data-testid="stElementContainer"]{justify-content:flex-start}.st-key-navradio [data-testid="stRadio"]{width:100%}}
@media (max-width:560px){.hero-wrap .eyebrow,.slip .eyebrow{font-size:12.5px}.why{grid-template-columns:1fr}}

/* ===== palette v2: colour with meaning (categories, priority, status, SLA) ===== */
:root{--orange:#F97C3C;--blue:#2F6FED;--blue-bg:#E3EBFD;--amber:#D98E04;--amber-bg:#FBEFD0;--coral:#E4572E;--coral-bg:#FCE3DA;--violet:#7A5AF8;--violet-bg:#ECE6FE;--cyan:#0E9EB3;--cyan-bg:#DAF2F6;--green:#2E9E5B;--green-bg:#DCF1E4;--slate:#64748B;--slate-bg:#E8ECF1}
.tag.b{background:var(--blue-bg);color:#1F4FB8;border-color:transparent}.tag.v{background:var(--violet-bg);color:#5B3FD0;border-color:transparent}.tag.cy{background:var(--cyan-bg);color:#0A7686;border-color:transparent}
.tag.am{background:var(--amber-bg);color:#8A5A00;border-color:transparent}.tag.cr{background:var(--coral-bg);color:#B93A16;border-color:transparent}.tag.sl{background:var(--slate-bg);color:#475569;border-color:transparent}.tag.gn{background:var(--green-bg);color:#1F7A44;border-color:transparent}
.pd.High::before{background:var(--coral)}.pd.Medium::before{background:var(--amber)}.pd.Low::before{background:var(--cyan);border:0}
.st::before{border-color:var(--c,var(--accent));background:conic-gradient(var(--c,var(--accent)) var(--p,0%),transparent 0)}.st.Open{--c:var(--blue)}.st.InProgress{--c:var(--amber)}.st.Resolved{--c:var(--green)}
.st-key-nav::after{border-bottom:0;height:3px;background:linear-gradient(90deg,#F97C3C,#E4572E 22%,#7A5AF8 45%,#2F6FED 68%,#0E9EB3 84%,#2E9E5B)}
.stApp .d1 em{background:linear-gradient(90deg,var(--accent) 5%,var(--blue) 60%,var(--violet));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent}
.slip{position:relative}.slip::before{content:"";position:absolute;right:-16px;top:-14px;width:84px;height:84px;background:repeating-linear-gradient(135deg,var(--orange) 0 9px,transparent 9px 20px);opacity:.9;z-index:-1;border-radius:4px}
.slip::after{content:"";position:absolute;left:-48px;bottom:-16px;width:56px;height:56px;background:repeating-linear-gradient(135deg,var(--blue) 0 8px,transparent 8px 18px);opacity:.85;z-index:-1;border-radius:4px}
.why>div:nth-child(1) .n{color:var(--orange)}.why>div:nth-child(2) .n{color:var(--blue)}.why>div:nth-child(3) .n{color:var(--violet)}.why>div:nth-child(4) .n{color:var(--green)}
.why>div{border-top:3px solid var(--line);padding-top:14px}.why>div:nth-child(1){border-color:var(--orange)}.why>div:nth-child(2){border-color:var(--blue)}.why>div:nth-child(3){border-color:var(--violet)}.why>div:nth-child(4){border-color:var(--green)}
.phil::after{background:linear-gradient(100deg,#F6EFE3,#EAF1FE 55%,#F1ECFE)}
.st-key-cta button{background:linear-gradient(90deg,var(--accent),#1F7A8C)!important}
/* ===== staff workspace ===== */
.st-key-queue [role="radiogroup"]{flex-direction:column;gap:4px}
.st-key-queue [data-testid="stRadioOption"]{padding:9px 12px;border-radius:6px;border:1px solid transparent;margin:0;background:transparent;width:100%}
.st-key-queue [data-testid="stRadioOption"]:hover{background:var(--sunk)}.st-key-queue [data-testid="stRadioOption"]>div>div:first-child{display:none}
.st-key-queue [data-testid="stRadioOption"][data-selected="true"]{background:var(--card);border-color:var(--line);box-shadow:inset 3px 0 0 var(--blue)}
.st-key-queue [data-testid="stRadioOption"] p{font:500 14px var(--sans)!important;color:var(--ink)!important;white-space:pre}
.trow{display:grid;grid-template-columns:5px 1fr;background:var(--card);border:1px solid var(--line);border-radius:6px;overflow:hidden;margin:0 0 6px}.trow .bar{background:var(--pc,var(--slate))}
.trow .body{padding:10px 12px}.trow .t{font-weight:600;line-height:1.3}.trow.sel{border-color:var(--blue);box-shadow:0 0 0 1px var(--blue)}
.trow .m{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:7px;font-size:12.5px;color:var(--mute)}.trow .m .tag{margin:0}
[class*="st-key-open_"] button{min-height:0;padding:3px 10px;font-size:12.5px;width:100%;white-space:nowrap}
.sla{font:500 11.5px var(--sans);padding:2px 8px;border-radius:999px;background:var(--slate-bg);color:#475569;white-space:nowrap}.sla.overdue,.sla.missed{background:var(--coral-bg);color:#B93A16}.sla.due_soon{background:var(--amber-bg);color:#8A5A00}.sla.met{background:var(--green-bg);color:#1F7A44}
.dh .id{font:500 12.5px ui-monospace,Consolas,monospace;color:var(--mute)}.dh .sum{font:600 28px/1.1 var(--serif);letter-spacing:-.02em;margin:6px 0 10px}
.sect{margin-top:22px}.sect .eyebrow{margin-bottom:8px}
.tl2{list-style:none;margin:0;padding:0 0 0 14px;border-left:2px solid var(--line)}.tl2 li{position:relative;padding:0 0 14px 14px;font-size:14.5px}
.tl2 li::before{content:"";position:absolute;left:-21px;top:5px;width:10px;height:10px;border-radius:50%;background:var(--card);border:2px solid var(--accent)}
.tl2 li.internal::before{background:var(--amber);border-color:var(--amber)}.tl2 li.public::before{background:var(--blue);border-color:var(--blue)}
.tl2 small{display:block;color:var(--mute);font-size:12px}.tl2 .nb{display:inline-block;margin-top:3px;padding:6px 10px;border-radius:6px;background:var(--slate-bg)}.tl2 li.internal .nb{background:var(--amber-bg)}.tl2 li.public .nb{background:var(--blue-bg)}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin:6px 0 18px}.kpis.three{grid-template-columns:repeat(3,1fr)}
.kpi{background:var(--card);border:1px solid var(--line);border-top:3px solid var(--k,var(--accent));border-radius:6px;padding:14px 16px}.kpi b{display:block;font:600 38px/1 var(--serif);color:var(--k,var(--ink))}.kpi span{color:var(--mute);font-size:13px}
.stack{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--slate-bg);margin:10px 0 8px}.stack i{display:block}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--mute)}.legend b{color:var(--ink)}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
.hl{display:grid;grid-template-columns:1fr auto;gap:6px 12px;font-size:14.5px}.hl div:nth-child(even){font-weight:600;text-align:right}
@media (max-width:960px){.kpis{grid-template-columns:repeat(2,1fr)}.kpis.three{grid-template-columns:1fr}}

/* ===== v3: sign-off lifecycle, pipeline log, stepper, confetti, student cards, auth portal ===== */
.st.PendingSign-off{--c:var(--violet);--p:75%}.st.Reopened{--c:var(--coral);--p:35%}
.term{background:#0F172A;color:#CBD5E1;border-radius:8px;padding:14px 16px;font:12.5px/1.8 ui-monospace,Consolas,monospace;margin:10px 0}.term b{color:#fff;font-weight:600}
.term .ok{color:#4ADE80}.term .warn{color:#FBBF24}.term .info{color:#7DD3FC}.term .dim{color:#94A3B8}.term .ttl{color:#94A3B8;text-transform:uppercase;letter-spacing:.12em;font-size:11px;margin-bottom:6px}
.stp{list-style:none;display:flex;margin:16px 0 8px;padding:0}.stp li{flex:1;text-align:center;position:relative;font-size:11.5px;color:var(--mute)}
.stp li i{display:block;width:14px;height:14px;border-radius:50%;margin:0 auto 7px;background:var(--card);border:2px solid var(--line);position:relative;z-index:1}
.stp li::before{content:"";position:absolute;top:6px;left:-50%;width:100%;height:2px;background:var(--line)}.stp li:first-child::before{display:none}
.stp li.done i{background:var(--green);border-color:var(--green)}.stp li.done::before{background:var(--green)}
.stp li.cur i{border-color:var(--blue);box-shadow:0 0 0 4px var(--blue-bg)}.stp li.cur{color:var(--ink);font-weight:600}.stp li.bad i{border-color:var(--coral);box-shadow:0 0 0 4px var(--coral-bg)}.stp li.bad{color:var(--coral);font-weight:600}
[class*="st-key-tk_"]{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--slate);border-radius:6px;padding:18px 20px;margin-bottom:14px}
[class*="st-key-tk_"]:has(.pcm-High){border-left-color:var(--coral)}[class*="st-key-tk_"]:has(.pcm-Medium){border-left-color:var(--amber)}[class*="st-key-tk_"]:has(.pcm-Low){border-left-color:var(--cyan)}
[class*="st-key-tk_"]:has(.pcm-wait){box-shadow:0 0 0 2px var(--violet-bg),0 8px 24px -14px rgba(122,90,248,.6)}
.tk-h{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px}.tk-h .id{font:500 12.5px ui-monospace,Consolas,monospace;color:var(--mute);margin-left:auto}
.tk-t{font:600 24px/1.15 var(--serif);letter-spacing:-.02em;margin:4px 0 6px}.tk-m{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:var(--mute);margin:8px 0}
.callout{border-radius:8px;padding:14px 16px;margin:12px 0}.callout.wait{background:var(--violet-bg);border:1px solid #D5CBFB}.callout.wait b{color:#5B3FD0}.callout.bad{background:var(--coral-bg);border:1px solid #F5C1B1}.callout.ok{background:var(--green-bg);border:1px solid #B8E0C6}
.banner{display:flex;gap:12px;align-items:center;background:var(--violet-bg);border:1px solid #D5CBFB;border-radius:8px;padding:12px 16px;margin:0 0 16px}.banner b{color:#5B3FD0}
.st-key-tfilter [role="radiogroup"]{gap:8px;flex-wrap:wrap}.st-key-tfilter [data-testid="stRadioOption"]{padding:5px 14px;border:1px solid var(--line);border-radius:999px;background:var(--card);margin:0}
.st-key-tfilter [data-testid="stRadioOption"]>div>div:first-child{display:none}.st-key-tfilter [data-testid="stRadioOption"] p{font:500 13px var(--sans)!important;color:var(--ink)!important}
.st-key-tfilter [data-testid="stRadioOption"][data-selected="true"]{background:var(--ink);border-color:var(--ink)}.st-key-tfilter [data-testid="stRadioOption"][data-selected="true"] p{color:var(--bg)!important}
.st-key-panel_auth{padding:22px 24px}.st-key-panel_auth .d3{font-size:26px;margin:0 0 4px}.authsub{color:var(--mute);font-size:14px;margin:0 0 10px}
.demo-h{font:500 11px var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--mute);margin:14px 0 8px;text-align:center}
.wel{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:14px 0}.wel div{background:var(--sunk);border-radius:8px;padding:12px}.wel b{display:block;font:600 30px/1 var(--serif)}.wel span{font-size:12.5px;color:var(--mute)}
.cf{position:fixed;inset:0;pointer-events:none;z-index:99999;overflow:hidden}.cf i{position:absolute;top:-16px;width:var(--s);height:calc(var(--s)*1.6);background:var(--c);opacity:0;border-radius:2px;animation:cf var(--t) ease-in var(--d) forwards}
@keyframes cf{0%{opacity:1;transform:translate3d(0,0,0) rotate(0)}100%{opacity:0;transform:translate3d(var(--x),108vh,0) rotate(var(--r))}}
@media (prefers-reduced-motion:reduce){.cf{display:none}}
.kpis.four{grid-template-columns:repeat(4,1fr)}.tl2 li.student::before{background:var(--green);border-color:var(--green)}.tl2 li.student .nb{background:var(--green-bg)}
@media (max-width:700px){.stp li{font-size:10px}.wel{grid-template-columns:1fr}}
@media (max-width:960px){.kpis.three,.kpis.four{grid-template-columns:repeat(2,1fr)!important}}

/* Responsive refinements: keep the existing editorial layout, avoid scroll/overflow on small screens. */
.stApp::before{background:radial-gradient(ellipse at 8% 8%,rgba(115,168,205,.14),transparent 38%),linear-gradient(180deg,#F5F8FA 0%,#FFFCF8 45%,#F7F5F0 100%)}
button[data-testid^="stBaseButton-primary"],button[data-testid^="stBaseButton-secondary"]{min-height:44px}
button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid rgba(47,111,237,.4)!important;outline-offset:2px}
.st-key-panel_auth,.st-key-panel_track,.st-key-panel_res,.st-key-panel_det,.st-key-panel_me{box-shadow:0 10px 30px -24px rgba(30,26,23,.34)}
.hero-p{line-height:1.65}
@media (max-width:960px){
  .block-container{max-width:100%!important}
  .st-key-panel_auth,.st-key-panel_track,.st-key-panel_res,.st-key-panel_det{padding:20px}
}
@media (max-width:700px){
  :root{--pad:16px}
  .block-container{padding:0 var(--pad) calc(92px + env(safe-area-inset-bottom))!important}
  .pgh{font-size:clamp(34px,9vw,48px)}
  .d1{font-size:clamp(42px,12vw,64px)}
  .hero-wrap{padding-top:38px}
  .hero-p{font-size:16px;margin-top:18px}
  .sec{padding:54px 0}
  .st-key-panel_auth,.st-key-panel_track,.st-key-panel_res,.st-key-panel_det,.st-key-panel_me{padding:16px}
  .kpis,.kpis.three,.kpis.four{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:8px}
  .kpi{padding:12px}.kpi b{font-size:30px}
  .tk-t{font-size:21px}.tk-m{gap:8px 12px;font-size:12px}
  .st-key-cta{left:var(--pad);right:var(--pad);width:auto!important;transform:none;bottom:calc(12px + env(safe-area-inset-bottom))}
  .st-key-cta button{width:100%}
  .stApp input,.stApp textarea{font-size:16px!important}
  [class*="st-key-tk_"]{padding:15px 14px}
}
@media (max-width:540px){
  .stApp [data-testid="stHorizontalBlock"]{flex-wrap:wrap}
  .stApp [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 100%!important;width:100%!important}
  .st-key-nav [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:0 1 auto!important;width:auto!important}
}
@media (prefers-reduced-motion:reduce){.cf{display:none}}
.campus-hero,.campus-page-banner{position:relative;overflow:hidden;border:1px solid rgba(230,223,212,.8);border-radius:18px;background-color:#07141C;background-size:cover;background-position:center 54%;box-shadow:0 14px 36px -30px rgba(30,55,68,.5)}
.campus-hero{isolation:isolate;background-image:linear-gradient(90deg,rgba(4,15,22,.78) 0%,rgba(4,15,22,.68) 48%,rgba(4,15,22,.16) 100%),url("app/static/resolveai-live-campus-bg.jpg");border-color:rgba(97,189,194,.35);padding:clamp(28px,5vw,58px);min-height:390px;display:flex;align-items:center}
.campus-page-banner{background-color:#EAF1F5;background-image:linear-gradient(90deg,rgba(255,252,248,.97) 0%,rgba(255,252,248,.9) 48%,rgba(255,252,248,.36) 100%),url("app/static/campus-background.jpg")}
.campus-hero-copy{position:relative;z-index:2;max-width:660px}.campus-hero .eyebrow{color:#8FE8DF}.campus-hero .d1{font-size:clamp(42px,6.5vw,76px);max-width:11ch;margin-top:16px;color:#F4FAFC}.campus-hero .d1 em{color:#46DBCC!important;background:none!important;-webkit-text-fill-color:#46DBCC!important}.campus-hero .hero-p{max-width:48ch;color:#D5E3E9!important}
.campus-hero .hero-tags{margin-top:24px;display:flex;gap:6px;flex-wrap:wrap}.campus-hero .hero-tags .tag{background:rgba(8,28,37,.7)!important;color:#EAF8F7!important;border:1px solid rgba(154,219,218,.24)}
.hero-network{position:absolute;inset:0;z-index:1;overflow:hidden;pointer-events:none;background:linear-gradient(113deg,transparent 31%,rgba(54,215,202,.12) 31.15%,transparent 31.5%),linear-gradient(158deg,transparent 67%,rgba(80,170,230,.12) 67.15%,transparent 67.5%);mask-image:linear-gradient(90deg,transparent 0%,#000 18%,#000 94%,transparent 100%)}
.live-dot{--dx:40px;--dy:-18px;position:absolute;left:var(--px);top:var(--py);width:5px;height:5px;border-radius:50%;background:#53F2DB;box-shadow:0 0 8px 3px rgba(66,230,213,.82),0 0 28px 9px rgba(30,191,196,.31);opacity:.74;animation:live-dot-drift var(--duration,9s) ease-in-out var(--delay,0s) infinite alternate;will-change:transform}
.live-dot::after{content:"";position:absolute;inset:-6px;border:1px solid rgba(95,238,222,.62);border-radius:50%;animation:live-dot-pulse 2.8s ease-out var(--delay,0s) infinite}
.live-dot-1{--px:9%;--py:29%;--dx:75px;--dy:-14px;--duration:8s;--delay:-2s}.live-dot-2{--px:28%;--py:18%;--dx:-54px;--dy:48px;--duration:11s;--delay:-5s;background:#FFC879}.live-dot-3{--px:52%;--py:33%;--dx:68px;--dy:17px;--duration:9s;--delay:-3s}.live-dot-4{--px:76%;--py:21%;--dx:-35px;--dy:52px;--duration:13s;--delay:-8s;background:#FFC879}.live-dot-5{--px:88%;--py:62%;--dx:-76px;--dy:-35px;--duration:10s;--delay:-4s}.live-dot-6{--px:37%;--py:77%;--dx:44px;--dy:-32px;--duration:12s;--delay:-6s;background:#FFC879}.live-dot-7{--px:17%;--py:82%;--dx:32px;--dy:-47px;--duration:9s;--delay:-1s}.live-dot-8{--px:65%;--py:73%;--dx:-42px;--dy:-21px;--duration:14s;--delay:-7s}
@keyframes live-dot-drift{to{transform:translate3d(var(--dx),var(--dy),0);opacity:1}}
@keyframes live-dot-pulse{0%{transform:scale(.45);opacity:.8}100%{transform:scale(2.3);opacity:0}}
.campus-hero::after{content:"CAMPUS NETWORK · LIVE";position:absolute;right:18px;bottom:16px;z-index:2;padding:7px 11px;border:1px solid rgba(126,215,208,.23);border-radius:99px;background:rgba(3,17,24,.52);color:#B3E7E2;font:500 9px var(--sans);letter-spacing:.14em;backdrop-filter:blur(8px)}
.st-key-landing_page .landing-sheet{position:relative;margin:16px 0;padding:clamp(24px,4vw,46px);border:1px solid var(--line);border-radius:22px;background:var(--bg);box-shadow:0 24px 70px -58px rgba(18,41,49,.5);transform-origin:50% 0;backface-visibility:hidden}
.st-key-landing_page .landing-sheet::before{display:none}
@keyframes landing-sheet-roll{0%{opacity:.68;transform:perspective(1400px) translate3d(0,48px,0) rotateX(6deg) scale(.975);filter:blur(1px)}58%{opacity:1;transform:perspective(1400px) translate3d(0,-5px,0) rotateX(-.7deg) scale(1);filter:blur(0)}100%{opacity:1;transform:perspective(1400px) translate3d(0,-16px,0) rotateX(-1.5deg) scale(.995);filter:blur(0)}}
@supports (animation-timeline:view()){.st-key-landing_page .landing-sheet{animation:landing-sheet-roll linear both;animation-timeline:view();animation-range:entry 0% cover 34%}}
.campus-page-banner{padding:32px clamp(20px,4vw,42px);margin:0 0 20px;background-position:center 58%}
.campus-page-banner .eyebrow{margin:0}.campus-page-banner .pgh{font-size:clamp(34px,4vw,52px);max-width:17ch}.campus-page-banner .lead{max-width:62ch;margin-bottom:0}
[class*="st-key-voice_box"]{background:rgba(255,255,255,.82);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:0 0 18px}
.voice-title{font:500 15px var(--sans);color:var(--ink);margin-bottom:3px}.voice-help{font-size:13px;color:var(--mute);margin-bottom:10px}
.voice-review{border-left:3px solid var(--accent);background:#EDF4F1;padding:11px 14px;border-radius:4px 10px 10px 4px;margin:10px 0;font-size:14px}
.st-key-nav::after{background:linear-gradient(90deg,#2F5D50,#5F9DAC);height:2px}
.stApp .d1 em{background:linear-gradient(90deg,#2F5D50,#527D8B);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent}
@media (max-width:700px){.campus-hero{min-height:330px;padding:22px;background-position:59% center}.campus-hero .d1{font-size:clamp(40px,12vw,62px);max-width:10ch}.campus-hero::after{right:12px;bottom:12px;font-size:8px}.st-key-landing_page .landing-sheet{padding:22px 18px;margin:12px 0;border-radius:17px}.campus-page-banner{padding:24px 20px;background-position:65% center}[class*="st-key-voice_box"]{padding:15px;margin-bottom:14px}}
@media(prefers-reduced-motion:reduce){.live-dot,.live-dot::after{animation:none!important}.st-key-landing_page .landing-sheet{animation:none!important;transform:none!important;filter:none!important}}
.st-key-help_chat{background:linear-gradient(145deg,#F1F7F5,#E8F0ED);border:1px solid #D5E2DC;border-radius:18px;padding:20px 22px 14px;margin:12px 0 20px;box-shadow:0 18px 42px -32px rgba(32,73,59,.45)}
.help-chat-heading{display:flex;align-items:center;gap:12px;padding:0 0 15px;border-bottom:1px solid #D7E3DE;margin-bottom:16px;color:var(--ink)}
.help-chat-mark{display:grid;place-items:center;width:42px;height:42px;flex:0 0 42px;border-radius:14px;background:var(--accent);color:white;font:500 22px var(--serif)}
.help-chat-heading b,.help-chat-heading small{display:block}.help-chat-heading b{font-size:15px}.help-chat-heading small{font-size:12px;color:var(--mute)}
.help-online{margin-left:auto;display:flex;align-items:center;gap:7px;font-size:12px;color:#466354}.help-online i{width:8px;height:8px;background:#38A169;border-radius:50%;box-shadow:0 0 0 3px #D8EEE0}
.help-welcome{display:flex;align-items:flex-start;gap:14px;max-width:520px;margin:22px 0 18px;padding:17px 19px;background:#fff;border:1px solid #DCE6E1;border-radius:16px 16px 16px 5px;box-shadow:0 5px 16px -14px rgba(30,26,23,.4)}
.help-welcome>span{font-size:22px}.help-welcome b{font-size:15px}.help-welcome p{margin:4px 0 0;color:var(--mute);font-size:13.5px}
.st-key-help_chat [data-testid="stChatMessage"]{background:#fff;border:1px solid #DCE6E1;border-radius:16px;padding:13px 16px;margin:10px 0;box-shadow:0 5px 16px -14px rgba(30,26,23,.4)}
.st-key-help_chat [data-testid="stChatMessage"] p{margin:0;line-height:1.65}
.st-key-help_chat [data-testid="stChatInput"]{background:#fff;border:1px solid #C8D8D0;border-radius:14px;box-shadow:0 4px 16px -12px rgba(30,26,23,.45)}
.st-key-help_chat [data-testid="stChatInput"] textarea{background:transparent!important}
.st-key-help_questions button{background:#fff;border:1px solid #D7E2DC;border-radius:12px;min-height:54px;box-shadow:0 3px 12px -10px rgba(30,26,23,.35);transition:transform .15s ease,border-color .15s ease,background .15s ease}
.st-key-help_questions button:hover{background:#F0F6F2;border-color:#8EB09D;transform:translateY(-1px)}
@media (max-width:700px){.st-key-help_chat{padding:15px 13px 10px;border-radius:15px}.help-chat-heading{gap:10px}.help-chat-mark{width:38px;height:38px;flex-basis:38px}.help-welcome{padding:14px}.st-key-help_questions button{min-height:48px}}

/* Compact shared navigation: brand first, calm full-width page links beneath. */
.st-key-nav{position:relative;z-index:5;margin:0 calc(-1 * var(--pad));padding:12px var(--pad) 0;background:rgba(255,252,248,.92);border-bottom:1px solid var(--line);backdrop-filter:blur(14px)}
.st-key-nav .nav-brand{display:flex;align-items:baseline;gap:12px;min-height:40px}
.st-key-nav .logo{font:500 24px/1 var(--serif);letter-spacing:-.045em;color:var(--ink)}
.st-key-nav .logo i{font-style:normal;color:var(--accent)}
.st-key-nav .nav-context{font:400 12px var(--sans);color:var(--mute);letter-spacing:.04em}
.st-key-nav .portal-chip{display:inline-flex;align-items:center;padding:6px 10px;border-radius:999px;font:600 10px var(--sans);letter-spacing:.1em;white-space:nowrap}
.st-key-nav .student-chip{background:#E4EFFD;color:#24569A;border:1px solid #C8D9F2}
.st-key-nav .staff-chip{background:#E4F1E8;color:#24613E;border:1px solid #C8DFD0}
.st-key-nav .worker-chip{background:#E3F3F2;color:#146B69;border:1px solid #B9DEDC}
.st-key-nav .guest-chip{background:#F3EEE5;color:#665641;border:1px solid #E4D9C8}
.st-key-navradio{padding:5px 0 0}
.st-key-navradio [role="radiogroup"]{gap:clamp(12px,2.2vw,30px);flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none}
.st-key-navradio [role="radiogroup"]::-webkit-scrollbar{display:none}
.st-key-navradio [data-testid="stRadioOption"]{flex:0 0 auto;padding:9px 0 11px;border-bottom:2px solid transparent}
.st-key-navradio [data-testid="stRadioOption"]>div>div:first-child{display:none}
.st-key-navradio [data-testid="stRadioOption"] p{font:500 12px var(--sans)!important;letter-spacing:.025em!important;text-transform:none!important;color:var(--mute)!important;white-space:nowrap}
.st-key-navradio [data-testid="stRadioOption"][data-selected="true"]{border-color:var(--accent)}
.st-key-navradio [data-testid="stRadioOption"][data-selected="true"] p{color:var(--accent)!important}
.st-key-nav::after{display:none}
.st-key-campus_layer [role="radiogroup"]{gap:8px;flex-wrap:wrap}
.st-key-campus_layer [data-testid="stRadioOption"]{padding:7px 14px;border:1px solid var(--line);border-radius:999px;background:#fff;margin:0}
.st-key-campus_layer [data-testid="stRadioOption"]>div>div:first-child{display:none}
.st-key-campus_layer [data-testid="stRadioOption"] p{font:500 13px var(--sans)!important;color:var(--mute)!important}
.st-key-campus_layer [data-testid="stRadioOption"][data-selected="true"]{background:var(--accent);border-color:var(--accent)}
.st-key-campus_layer [data-testid="stRadioOption"][data-selected="true"] p{color:#fff!important}
.campus-intro{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;margin:20px 0 18px;padding:24px 28px;border:1px solid #D9E5DE;border-radius:18px;background:linear-gradient(120deg,rgba(235,244,238,.96),rgba(242,246,248,.9)),radial-gradient(circle at 90% 10%,#fff,transparent 40%);box-shadow:0 14px 35px -30px rgba(32,73,59,.5)}
.campus-intro .eyebrow{margin-bottom:8px}.campus-intro .pgh{font:600 clamp(30px,4vw,44px)/1.08 var(--serif);letter-spacing:-.03em;margin:0}.campus-intro p{max-width:62ch;color:var(--mute);font-size:14px;margin:8px 0 0}.campus-badge{flex:0 0 auto;padding:8px 12px;border:1px solid #D4E2D9;border-radius:999px;background:rgba(255,255,255,.72);color:#466354;font-size:12px;white-space:nowrap}
.campus-map-frame{padding:8px;border:1px solid var(--line);border-radius:16px;background:white;box-shadow:0 15px 38px -32px rgba(30,26,23,.42);overflow:hidden}
.campus-map-frame iframe{border-radius:10px}
.campus-insight-panel{padding:18px!important;border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.88);box-shadow:0 14px 38px -32px rgba(30,26,23,.45);min-height:100%}
.campus-place{display:grid;grid-template-columns:26px 1fr auto;align-items:center;gap:2px 8px;padding:12px 0;border-bottom:1px solid #ECE8E1}
.campus-rank{grid-row:span 2;color:#8A9690;font:500 11px ui-monospace,Consolas,monospace}
.campus-place-name{font-size:13px;font-weight:600;line-height:1.3;overflow-wrap:anywhere}
.campus-place-count{font:500 16px var(--serif);color:var(--accent);white-space:nowrap}.campus-place-count small{font:400 10px var(--sans);color:var(--mute)}
.campus-place-meta{grid-column:2/4;font-size:11px;color:var(--mute)}
.campus-empty{padding:18px 12px;text-align:center;border:1px dashed var(--line);border-radius:10px;color:var(--mute);font-size:13px}
.campus-legend{display:flex;gap:10px 14px;flex-wrap:wrap;margin:15px 0 8px;color:var(--mute);font-size:11px}.campus-legend span{display:flex;align-items:center;gap:5px}.campus-legend i{width:8px;height:8px;border-radius:50%;display:inline-block}.campus-legend i.hot{background:#E4572E}.campus-legend i.open{background:#F0A33B}.campus-legend i.done{background:#2E9E5B}
.staff-hero{display:flex;justify-content:space-between;align-items:center;gap:20px;margin:22px 0 12px;padding:23px 28px;border-radius:18px;border:1px solid #D9E5DE;background:linear-gradient(120deg,#EEF5F0,#F4F6F8);box-shadow:0 16px 38px -34px rgba(32,73,59,.5)}
.staff-title{font:600 clamp(30px,4vw,42px)/1.1 var(--serif);letter-spacing:-.03em;margin-top:5px}
.staff-hero p{font-size:13.5px;color:var(--mute);margin:7px 0 0}.staff-hero p b{color:var(--ink);font-weight:600}
.staff-live{display:flex;align-items:center;gap:8px;padding:8px 12px;border:1px solid #D5E2D9;border-radius:999px;background:rgba(255,255,255,.72);color:#466354;font-size:12px;white-space:nowrap}
.staff-live i{width:8px;height:8px;background:#2E9E5B;border-radius:50%;box-shadow:0 0 0 3px #D8EEE0}
.anonymous-note{display:flex;flex-direction:column;gap:3px;margin:12px 0;padding:12px 14px;border-radius:10px;border:1px solid #C7D8EF;border-left:4px solid #3978C5;background:#EDF4FD;color:#24476F;font-size:13px}.anonymous-note span{color:#506783;font-size:12px}
.st-key-student_portal{margin:14px 0 26px;padding:clamp(12px,2vw,24px);border:1px solid #D9E6F4;border-radius:20px;background:linear-gradient(155deg,rgba(236,244,253,.94),rgba(249,251,254,.84) 50%,rgba(236,247,249,.84));box-shadow:0 20px 50px -42px rgba(37,91,147,.34)}
.st-key-student_portal [data-testid="stBaseButton-primary"]{background:#2F6FED!important;border-color:#2F6FED!important}.st-key-student_portal [data-testid="stBaseButton-primary"]:hover{background:#245BBF!important;border-color:#245BBF!important}
.st-key-staff_portal{margin:14px 0 26px;padding:clamp(12px,2vw,24px);border:1px solid #D9E6DE;border-radius:20px;background:linear-gradient(155deg,rgba(235,244,238,.92),rgba(249,251,249,.86) 54%,rgba(233,241,237,.88));box-shadow:0 20px 50px -42px rgba(38,88,58,.34)}
.student-portal-banner{display:flex;align-items:center;gap:16px;margin:20px 0 18px;padding:22px 24px;border:1px solid #2356A0;border-left:6px solid #17427E;border-radius:16px;background:linear-gradient(112deg,#24599A 0%,#2F6FED 56%,#287F9B 100%);box-shadow:0 18px 38px -24px rgba(29,74,137,.6)}
.student-mark{display:grid;place-items:center;flex:0 0 48px;width:48px;height:48px;border-radius:15px;background:#F5F8FF;color:#24599A;font:700 20px var(--sans);box-shadow:0 6px 18px -8px rgba(5,25,56,.55)}
.student-portal-banner .eyebrow{color:#D8E7FF;margin:0 0 5px;font-size:10px;letter-spacing:.15em}
.student-banner-title{font:600 23px/1.15 var(--sans);letter-spacing:-.025em;color:#fff}
.student-portal-banner p{margin:5px 0 0;color:#E2EDFF;font-size:13px;line-height:1.45}
.student-banner-step{margin-left:auto;display:flex;align-items:baseline;gap:7px;color:#24569A;font:500 19px var(--serif);white-space:nowrap}
.student-banner-step span{font:600 9px var(--sans);letter-spacing:.13em}
.staff-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0 22px}
.staff-metrics .kpi{padding:12px 15px;border-top-width:2px;border-radius:12px;box-shadow:0 7px 20px -20px rgba(30,26,23,.55)}
.staff-metrics .kpi b{font-size:32px}.staff-metrics .kpi span{font-size:11.5px;letter-spacing:.02em}
.st-key-worker_portal{margin:14px 0 26px;padding:clamp(12px,2vw,24px);border:1px solid #CDE2E1;border-radius:20px;background:linear-gradient(155deg,rgba(230,244,243,.96),rgba(248,251,251,.88) 55%,rgba(233,244,242,.9));box-shadow:0 20px 50px -42px rgba(20,105,101,.34)}
.worker-hero{display:flex;align-items:center;gap:18px;margin:8px 0 16px;padding:23px 26px;border:1px solid #1C6565;border-radius:17px;background:linear-gradient(112deg,#124C58 0%,#176B72 58%,#248B84 100%);color:#F4FFFF;box-shadow:0 18px 38px -27px rgba(15,77,81,.55)}
.worker-icon{display:grid;place-items:center;width:52px;height:52px;flex:0 0 52px;border-radius:16px;background:#D8F1E9;color:#125E5B;font:700 20px var(--sans)}
.worker-hero-copy{min-width:0;flex:1}.worker-hero .eyebrow{font-size:10px;letter-spacing:.16em;color:#BDE4DB;margin:0 0 5px}.worker-title{font:500 clamp(26px,3.5vw,38px)/1.05 var(--serif);letter-spacing:-.025em;color:#F7FFFF}.worker-hero p{margin:7px 0 0;color:#D5ECE8;font-size:13px}.worker-hero p b{color:#fff}
.worker-role-badge{padding:9px 13px;border:1px solid rgba(220,251,245,.3);border-radius:12px;background:rgba(255,255,255,.08);font:600 10px var(--sans);letter-spacing:.12em;color:#D8F2EC;text-align:center;white-space:nowrap}.worker-role-badge b{display:inline-block;margin-top:4px;font-size:9px;color:#B8E2D9}
.worker-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:0 0 16px}.worker-metrics div{padding:12px 15px;border:1px solid #D8E7E5;border-radius:12px;background:rgba(255,255,255,.78)}.worker-metrics b{display:block;font:500 30px/1 var(--serif);color:#156F6C}.worker-metrics span{font-size:12px;color:#526B69}.worker-metrics .urgent b{color:#C4482C}
.worker-task-card{margin:12px 0 16px;padding:19px 21px;border:1px solid #D5E5E3;border-radius:14px;background:var(--card);box-shadow:0 14px 34px -30px rgba(20,70,71,.35)}.worker-task-meta{display:flex;align-items:center;gap:7px;flex-wrap:wrap;color:var(--mute);font-size:12px}.worker-task-meta>span:first-child{font:500 12px ui-monospace,Consolas,monospace}.worker-deadline{margin-left:auto}.worker-task-title{margin:12px 0 7px;font:500 clamp(22px,3vw,30px)/1.16 var(--serif);letter-spacing:-.02em;color:var(--ink)}.worker-task-description{font-size:14px;line-height:1.58;color:var(--ink);white-space:pre-wrap;overflow-wrap:anywhere}.worker-task-location{display:grid;grid-template-columns:auto 1fr auto 1fr auto 1fr;gap:8px 12px;align-items:center;margin-top:15px;padding-top:12px;border-top:1px solid var(--line);font-size:12px}.worker-task-location b{color:var(--mute);font-weight:500}.worker-task-location span{color:var(--ink)}.worker-empty{display:flex;flex-direction:column;gap:6px;margin:18px 0;padding:24px;border:1px dashed #B8D3D1;border-radius:14px;background:rgba(255,255,255,.55);color:#1C5654}.worker-empty span{font-size:13px;color:#526B69}
.stApp [data-testid="stTabs"] [role="tablist"]{gap:6px;border:0;background:#F0EEE9;padding:5px;border-radius:12px;width:max-content;max-width:100%;overflow-x:auto}
.stApp [data-testid="stTabs"] [data-testid="stTab"]{padding:8px 16px;border:0;border-radius:9px;white-space:nowrap}
.stApp [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]{background:#fff;box-shadow:0 2px 8px rgba(30,26,23,.08)}
.stApp [data-testid="stTabs"] [data-testid="stTab"] p{letter-spacing:.02em;text-transform:none;font-size:13px!important}
.st-key-queue [data-baseweb="select"]>div{border-radius:10px!important;background:#fff!important}
.st-key-panel_det{border-radius:14px!important;padding:24px!important;box-shadow:0 15px 40px -34px rgba(30,26,23,.55)}
.st-key-panel_det .dh .sum{font-size:clamp(23px,2.5vw,31px)}
.st-key-panel_det .sect{padding-top:8px;border-top:1px solid #EEEAE4}
.st-key-panel_det [data-testid="stExpander"]{border-radius:10px;border-color:var(--line);background:rgba(255,255,255,.65)}
.st-key-panel_det [data-testid="stTextArea"] textarea{border-radius:10px!important}
.st-key-panel_det .tl2{margin-top:9px}
.st-key-panel_c1,.st-key-panel_c2,.st-key-panel_c3,.st-key-panel_c4,.st-key-panel_sys1,.st-key-panel_sys2{border-radius:14px!important;box-shadow:0 12px 30px -28px rgba(30,26,23,.5)}
@media(max-width:700px){.st-key-nav{padding-top:10px}.st-key-nav .nav-context{display:none}.st-key-navradio [role="radiogroup"]{gap:18px}.st-key-navradio [data-testid="stRadioOption"]{padding:8px 0 10px}.campus-intro{display:block;padding:19px 18px;margin-top:14px}.campus-badge{display:inline-block;margin-top:14px}.st-key-campus_layer [role="radiogroup"]{gap:6px}.st-key-campus_layer [data-testid="stRadioOption"]{padding:6px 10px}.campus-map-frame{padding:4px;border-radius:12px}}
@media(max-width:700px){.staff-hero{display:block;padding:19px 18px;margin-top:14px}.staff-live{display:inline-flex;margin-top:14px}.staff-metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:16px}.staff-metrics .kpi{padding:10px 11px}.staff-metrics .kpi b{font-size:28px}.stApp [data-testid="stTabs"] [role="tablist"]{width:100%;justify-content:flex-start}.stApp [data-testid="stTabs"] [data-testid="stTab"]{padding:7px 12px}.st-key-campus_insight_panel{margin-top:14px}.st-key-panel_det{padding:16px!important}.st-key-nav .nav-context{display:inline-flex}.st-key-nav .portal-chip{font-size:9px;padding:5px 7px}.student-portal-banner{gap:11px;padding:14px 13px;margin:14px 0 12px}.student-mark{flex-basis:36px;width:36px;height:36px;border-radius:11px}.student-banner-title{font-size:18px}.student-portal-banner p{font-size:12px}.student-banner-step{font-size:16px}.student-banner-step span{font-size:8px}}
@media(max-width:700px){.st-key-student_portal,.st-key-staff_portal{padding:12px;margin-top:8px;border-radius:14px}.student-portal-banner{border-radius:12px}.anonymous-note{padding:10px 11px}}
@media(max-width:700px){.st-key-worker_portal{padding:12px;margin-top:8px;border-radius:14px}.worker-hero{gap:12px;padding:17px 15px;border-radius:13px}.worker-icon{width:40px;height:40px;flex-basis:40px;border-radius:12px}.worker-role-badge{font-size:8px;padding:7px 8px}.worker-metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.worker-metrics div{padding:10px}.worker-metrics b{font-size:24px}.worker-metrics span{font-size:11px}.worker-task-card{padding:15px 14px}.worker-deadline{margin-left:0}.worker-task-location{grid-template-columns:auto 1fr;gap:7px 12px}.st-key-nav .worker-chip{max-width:48vw;overflow:hidden;text-overflow:ellipsis}}
"""

DARK_THEME_CSS = """
:root{color-scheme:dark;--bg:#101713;--card:#19231D;--sunk:#202D25;--ink:#F0F4EF;--mute:#B2C0B6;--line:#35443A;--accent:#A8CC8A;--clay:#FF9E83;--clay-bg:#3B2823;--ochre:#F3D17E;--ochre-bg:#3A321E;--ok-bg:#20382B;--blue:#8FB4FF;--blue-bg:#243753;--amber:#F3C66F;--amber-bg:#3B321D;--coral:#FF9A7D;--coral-bg:#422821;--violet:#C1A9FF;--violet-bg:#33294B;--cyan:#83D8E5;--cyan-bg:#203941;--green:#8ED3A2;--green-bg:#203A2A;--slate:#B1BEC9;--slate-bg:#2B3740}
html,body,.stApp,[data-testid="stAppViewContainer"]{background:var(--bg)!important;color:var(--ink)!important}
.stApp::before{background:radial-gradient(ellipse at 10% 12%,rgba(95,145,112,.16),transparent 38%),radial-gradient(ellipse at 88% 62%,rgba(120,93,157,.1),transparent 36%),linear-gradient(180deg,#101713 0%,#121A15 48%,#101713 100%)!important}
.stApp p,.stApp li,.stApp label,.stApp [data-testid="stMarkdownContainer"],.stApp [data-testid="stWidgetLabel"] p{color:var(--ink)}
.stApp .eyebrow,.stApp .lead,.stApp .note,.stApp .caption,.stApp small,.stApp .trow .m,.stApp .tk-m{color:var(--mute)}
.stApp .pgh,.stApp .d1,.stApp .d2,.stApp .d3,.stApp .big,.stApp .fbig{color:var(--ink)}
.stApp .campus-hero{background-image:linear-gradient(90deg,rgba(4,15,22,.78) 0%,rgba(4,15,22,.68) 48%,rgba(4,15,22,.16) 100%),url("app/static/resolveai-live-campus-bg.jpg")!important;border-color:rgba(97,189,194,.35)!important}
.stApp .campus-page-banner{background-image:linear-gradient(90deg,rgba(17,38,31,.96) 0%,rgba(17,38,31,.86) 55%,rgba(17,38,31,.5) 100%),url("app/static/campus-background.jpg")!important;border-color:#354C3D!important}
.stApp .campus-page-banner .eyebrow{color:#C4E5A2!important}.stApp .campus-page-banner .pgh{color:#F5F7F1!important}.stApp .campus-page-banner .lead{color:#D5E1D7!important}
.st-key-nav{background:rgba(16,23,19,.94)!important;border-color:var(--line)!important;box-shadow:0 0 0 100vmax rgba(16,23,19,.94)!important}
.st-key-nav .logo{color:var(--ink)}.st-key-nav .logo i{color:#B8DA91}.st-key-nav .nav-context{color:var(--mute)}
.st-key-nav .student-chip{background:#203753!important;color:#B8D2FF!important;border-color:#3A587C!important}.st-key-nav .staff-chip{background:#203A2A!important;color:#B7E8C3!important;border-color:#42694F!important}.st-key-nav .guest-chip{background:#2B302A!important;color:#D8D4C8!important;border-color:#48483D!important}
.stApp .student-portal-banner{background:linear-gradient(112deg,#17385F,#24519B 56%,#1D596B)!important;border-color:#3B6398!important;border-left-color:#8FB4FF!important}.stApp .student-mark{background:#EFF5FF!important;color:#24599A!important}.stApp .student-banner-title{color:#FFFFFF!important}.stApp .student-portal-banner p{color:#E2EDFF!important}.stApp .student-portal-banner .eyebrow,.stApp .student-banner-step{color:#C6DCFF!important}.stApp .anonymous-note{background:#1D2D40!important;border-color:#3B5879!important;border-left-color:#8FB4FF!important;color:#E7F0FF!important}.stApp .anonymous-note span{color:#C0CCDA!important}
.stApp .st-key-student_portal{background:linear-gradient(155deg,rgba(23,39,57,.94),rgba(24,32,42,.9) 55%,rgba(22,42,47,.88))!important;border-color:#354C64!important}.stApp .st-key-staff_portal{background:linear-gradient(155deg,rgba(21,44,33,.94),rgba(23,33,27,.9) 55%,rgba(21,42,32,.88))!important;border-color:#385747!important}.stApp .st-key-student_portal [data-testid="stBaseButton-primary"]{background:#8FB4FF!important;border-color:#8FB4FF!important}.stApp .st-key-student_portal [data-testid="stBaseButton-primary"] p{color:#14253A!important}
.stApp .st-key-worker_portal{background:linear-gradient(155deg,rgba(19,46,48,.95),rgba(23,34,36,.91) 55%,rgba(20,43,42,.89))!important;border-color:#35585A!important}.stApp .worker-hero{background:linear-gradient(112deg,#103B47,#15575E 58%,#1C706C)!important;border-color:#32676A!important}.stApp .worker-task-card{border-color:#3B5553!important}.stApp .worker-task-location{border-color:#35443A!important}.stApp .worker-metrics div,.stApp .worker-empty{background:rgba(25,35,29,.86)!important;border-color:#354C4B!important}.stApp .worker-metrics span,.stApp .worker-empty span{color:#B2C0B6!important}.stApp .worker-metrics b{color:#8ED3CC!important}.stApp .worker-metrics .urgent b{color:#FF9A7D!important}.stApp .worker-empty{color:#D9F4F0!important}.stApp .st-key-nav .worker-chip{background:#203A3A!important;color:#9DDBD6!important;border-color:#3E6663!important}
.st-key-navradio [data-testid="stRadioOption"] p{color:var(--mute)!important}.st-key-navradio [data-testid="stRadioOption"][data-selected="true"] p{color:#C4E5A2!important}
.st-key-nav [data-testid="stToggle"] label,.st-key-nav [data-testid="stToggle"] p{color:var(--mute)!important}
.stApp button[data-testid^="stBaseButton-primary"]{background:#A8CC8A!important;border-color:#A8CC8A!important;color:#152219!important}.stApp button[data-testid^="stBaseButton-primary"] p{color:#152219!important}
.stApp button[data-testid^="stBaseButton-secondary"]{background:#18221C!important;border-color:#829889!important;color:var(--ink)!important}.stApp button[data-testid^="stBaseButton-secondary"] p{color:var(--ink)!important}.stApp button[data-testid^="stBaseButton-secondary"]:hover{background:#25352B!important}
.stApp input,.stApp textarea,.stApp [data-baseweb="select"] input{color:var(--ink)!important;caret-color:#C4E5A2!important}.stApp input::placeholder,.stApp textarea::placeholder{color:#9AA99F!important;opacity:1}
.stApp div[data-baseweb="input"],.stApp div[data-baseweb="textarea"],.stApp div[data-baseweb="select"]>div,.stApp [data-testid="stTextInputRootElement"],.stApp [data-testid="stTextAreaRootElement"],.stApp [data-testid="stSelectbox"] [data-baseweb="select"]>div,.stApp [data-testid="stMultiSelect"] [data-baseweb="select"]>div{background:#18221C!important;border-color:#405347!important;color:var(--ink)!important}
.stApp [data-baseweb="tag"]{background:#2B3B30!important;color:#EAF4E4!important;border-color:#405347!important}.stApp [data-baseweb="tag"] span{color:#EAF4E4!important}.stApp [data-baseweb="tag"] svg{fill:#C5D5C9!important}
.stApp [data-testid="stAlertContainer"]{background:#202D25!important;border-color:#405347!important;border-left-color:#A8CC8A!important;color:var(--ink)!important}.stApp [data-testid="stAlertContainer"] *{color:var(--ink)!important}
.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]){background:#352E1D!important;border-left-color:#E0B653!important}.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]){background:#392720!important;border-left-color:#E77B5E!important}.stApp [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]){background:#20382B!important;border-left-color:#77BD8B!important}
.stApp [data-testid="stExpander"],.stApp details{background:rgba(25,35,29,.82)!important;border-color:var(--line)!important;color:var(--ink)!important}.stApp [data-testid="stExpander"] summary,.stApp [data-testid="stExpander"] summary p{color:var(--ink)!important}
.stApp [data-testid="stTabs"] [role="tablist"]{background:#202D25!important;border-color:var(--line)!important}.stApp [data-testid="stTabs"] [data-testid="stTab"] p{color:var(--mute)!important}.stApp [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]{background:#2B3B30!important;box-shadow:none!important}.stApp [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] p{color:#EAF4E4!important}
.stApp [role="radiogroup"] label,.stApp [role="radiogroup"] p,.stApp [data-testid="stCheckbox"] label,.stApp [data-testid="stCheckbox"] p{color:var(--ink)!important}
.stApp [data-testid="stToggle"] input{accent-color:#A8CC8A}
.stApp [data-testid="stMetric"] label,.stApp [data-testid="stMetric"] [data-testid="stMetricLabel"]{color:var(--mute)!important}.stApp [data-testid="stMetricValue"]{color:var(--ink)!important}
.stApp table,.stApp th,.stApp td{color:var(--ink)!important;border-color:var(--line)!important}.stApp [role="listbox"],.stApp [data-baseweb="popover"]>div,.stApp [data-baseweb="menu"]{background:#1C2821!important;color:var(--ink)!important;border-color:var(--line)!important}.stApp [role="option"]{color:var(--ink)!important}.stApp [role="option"]:hover{background:#2B3B30!important}
.stApp [data-testid="stDialog"] [role="dialog"],.stApp [role="dialog"]{background:var(--card)!important;color:var(--ink)!important;border-color:var(--line)!important}.stApp [data-testid="stFileUploader"] section{background:#18221C!important;border-color:#405347!important;color:var(--ink)!important}.stApp [data-testid="stFileUploader"] *{color:var(--ink)}
.stApp [class*="st-key-panel"]{background:var(--card)!important;border-color:var(--line)!important}.st-key-okpanel,.stApp .callout.ok{background:#20382B!important;border-color:#42694F!important;color:#DDF2E2!important}
.stApp .callout.wait,.stApp .banner{background:#302A42!important;border-color:#594B79!important;color:#EEE6FF!important}.stApp .callout.wait b,.stApp .banner b{color:#D1BDFF!important}.stApp .callout.bad{background:#392720!important;border-color:#704236!important;color:#FFE7DE!important}.stApp .callout.bad b{color:#FFB39A!important}
.stApp .tag{border-color:transparent!important}.stApp .tag.g,.stApp .tag.gn{background:#203A2A!important;color:#B7E8C3!important}.stApp .tag.o,.stApp .tag.am{background:#3A321E!important;color:#F5D989!important}.stApp .tag.c,.stApp .tag.cr{background:#422821!important;color:#FFB19A!important}.stApp .tag.b{background:#243753!important;color:#B8CEFF!important}.stApp .tag.v{background:#33294B!important;color:#D3C2FF!important}.stApp .tag.cy{background:#203941!important;color:#A0E4EC!important}.stApp .tag.sl{background:#2B3740!important;color:#CCD7E0!important}
.stApp .sla{background:#2B3740!important;color:#D5DEE6!important}.stApp .sla.overdue,.stApp .sla.missed{background:#422821!important;color:#FFB19A!important}.stApp .sla.due_soon{background:#3A321E!important;color:#F5D989!important}.stApp .sla.met{background:#203A2A!important;color:#B7E8C3!important}
.stApp .trow,.stApp [class*="st-key-tk_"]{background:#19231D!important;border-color:var(--line)!important}.stApp .trow .body,.stApp .trow .m,.stApp .dh .id,.stApp .ph{color:var(--mute)!important}.stApp .trow .t,.stApp .dh .sum,.stApp .tk-t{color:var(--ink)!important}
.stApp .kpi,.stApp .stats div,.stApp .wel div,.stApp .campus-insight-panel,.st-key-campus_insight_panel,.st-key-campus_map_frame{background:#19231D!important;border-color:var(--line)!important}.stApp .kpi span,.stApp .stats span,.stApp .wel span{color:var(--mute)!important}.stApp .stats,.stApp .stack,.stApp .tw{background:#202D25!important;border-color:var(--line)!important}
.stApp .kpi b{color:color-mix(in srgb,var(--k,var(--ink)) 58%,#fff)!important}.stApp .wel b[style*="color:#7A5AF8"]{color:#C1A9FF!important}.stApp .wel b[style*="color:#2E9E5B"]{color:#8ED3A2!important}.stApp .wel b[style*="color:#E4572E"]{color:#FF9A7D!important}.stApp [style*="color:#6F675F"]{color:#B2C0B6!important}
.stApp .proof-strip{border-color:var(--line)}.stApp .proof-strip span{color:var(--ink)}.stApp .proof-strip b{background:#263A2B;color:#C4E5A2}.stApp .phil::after{background:linear-gradient(105deg,#1B2820,#1C2B27 55%,#252439)!important}
.stApp .dupc{background:#352E1D!important;border-color:#705B2B!important;color:var(--ink)!important}.stApp .dupc small{color:var(--mute)!important}
.stApp .campus-intro,.stApp .staff-hero{background:linear-gradient(112deg,#152C24 0%,#1D382D 72%,#274538 100%)!important;border-color:#385747!important}.stApp .campus-intro .pgh,.stApp .staff-title{color:#F5F7F1!important}.stApp .campus-intro p,.stApp .staff-hero p{color:#D5E1D7!important}.stApp .campus-intro .eyebrow,.stApp .staff-hero .eyebrow{color:#C4E5A2!important}.stApp .campus-badge,.stApp .staff-live{color:#E5F0E5!important;background:rgba(255,255,255,.08)!important;border-color:rgba(255,255,255,.2)!important}
.stApp .st-key-campus_layer [data-testid="stRadioOption"][data-selected="true"] p{color:#152219!important}
.stApp .campus-place{border-color:#35443A}.stApp .campus-place-name{color:var(--ink)}.stApp .campus-place-meta,.stApp .campus-place-count small{color:var(--mute)}.stApp .campus-empty{border-color:var(--line);color:var(--mute)}.stApp .campus-legend{color:var(--mute)}
.stApp .st-key-help_chat{background:linear-gradient(145deg,#1A2B22,#1B2825)!important;border-color:#354C3D!important}.stApp .st-key-help_chat [data-testid="stChatMessage"],.stApp .help-welcome{background:#202D25!important;border-color:#35443A!important;color:var(--ink)!important}.stApp .help-chat-heading,.stApp .help-chat-heading b{color:var(--ink)!important}.stApp .help-chat-heading small{color:var(--mute)!important}.stApp .st-key-help_chat [data-testid="stChatInput"]{background:#18221C!important;border-color:#405347!important}.stApp .st-key-help_questions button{background:#202D25!important;border-color:#405347!important;color:var(--ink)!important}.stApp .voice-review{background:#20382B!important;color:#E3F0E5!important}
.stApp hr{border-color:var(--line)!important}.stApp a{color:#B8D8FF}
/* Keep older custom panels, status copy and Streamlit chrome on the same dark palette. */
.stApp [class*="st-key-panel"],.stApp .st-key-okpanel,.stApp .st-key-voice_box,.stApp [class*="st-key-tk_"]{background-color:var(--card)!important;border-color:var(--line)!important;color:var(--ink)!important}
.stApp .voice-review{background:#20382B!important;border-color:#42694F!important;color:#E3F0E5!important}
.stApp .callout.wait,.stApp .banner{border-color:#594B79!important}.stApp .callout.wait b,.stApp .banner b{color:#D1BDFF!important}
.stApp .callout.bad{border-color:#704236!important}.stApp .callout.bad b{color:#FFB39A!important}
.stApp .help-online{color:#B9D7C4!important}.stApp .help-online i{box-shadow:0 0 0 3px #263A2B!important}
.stApp .st-key-campus_layer [data-testid="stRadioOption"]{background:#19231D!important;border-color:var(--line)!important}.stApp .st-key-campus_layer [data-testid="stRadioOption"] p{color:var(--mute)!important}.stApp .st-key-campus_layer [data-testid="stRadioOption"][data-selected="true"]{background:#A8CC8A!important;border-color:#A8CC8A!important}.stApp .st-key-campus_layer [data-testid="stRadioOption"][data-selected="true"] p{color:#152219!important}
.stApp [data-testid="stDateInput"] input,.stApp [data-testid="stTimeInput"] input,.stApp [data-testid="stNumberInput"] input{background:#18221C!important;color:var(--ink)!important;border-color:#405347!important}
.stApp [data-testid="stDataFrame"],.stApp [data-testid="stTable"],.stApp [data-testid="stCode"]{background:#19231D!important;color:var(--ink)!important;border-color:var(--line)!important}
.stApp pre,.stApp code{background:#202D25!important;color:#E5EDE7!important;border-color:var(--line)!important}
.stApp [data-testid="stNotification"],.stApp [data-testid="stToast"]{background:#202D25!important;color:var(--ink)!important;border:1px solid var(--line)!important}
.stApp button:focus-visible,.stApp a:focus-visible,.stApp input:focus-visible,.stApp textarea:focus-visible,[role="radio"]:focus-visible,[role="tab"]:focus-visible{outline:3px solid #A8CC8A!important;outline-offset:2px!important}
.stApp button:disabled{opacity:.55!important;filter:saturate(.65)}
@media(max-width:700px){
  .st-key-nav [data-testid="stHorizontalBlock"]{align-items:center;gap:8px!important}
  .st-key-nav [data-testid="stToggle"] label p{font-size:11px!important}
  .st-key-navradio{overflow-x:auto;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch}
  .st-key-navradio [role="radiogroup"]{width:max-content;min-width:100%;padding-bottom:3px}
  .stApp [data-testid="stMainBlockContainer"]{padding-left:16px!important;padding-right:16px!important}
  .stApp .campus-hero,.stApp .campus-page-banner{background-position:62% center;padding:22px 18px}
  .stApp .campus-hero{min-height:280px}
  .stApp .campus-hero .d1{font-size:clamp(34px,9vw,46px)!important;line-height:1.02;max-width:13ch}
  .stApp .st-key-panel_auth{padding:18px 15px}
  .stApp .st-key-help_chat{padding:15px 12px 10px}
  .stApp .campus-insight-panel,.stApp .st-key-campus_insight_panel{padding:14px!important}
  .stApp .worker-hero{align-items:flex-start;flex-wrap:wrap}
  .stApp .worker-hero{display:grid;grid-template-columns:40px minmax(0,1fr);gap:10px 12px}
  .stApp .worker-icon{grid-column:1;grid-row:1;width:40px;height:40px;flex-basis:40px}
  .stApp .worker-hero-copy{grid-column:2;grid-row:1;min-width:0}
  .stApp .worker-role-badge{grid-column:2;grid-row:2;justify-self:start;margin:0}
  .stApp .worker-task-location{grid-template-columns:minmax(74px,auto) minmax(0,1fr)}
  .stApp .st-key-help_questions [data-testid="stHorizontalBlock"]{flex-wrap:wrap}
  .stApp .st-key-help_questions [data-testid="column"]{min-width:min(100%,220px)!important}
}
@media(max-width:420px){
  .st-key-nav .logo{font-size:21px!important}
  .st-key-nav .portal-chip{max-width:42vw;font-size:8px!important}
  .stApp .student-banner-step{display:none}
  .stApp .student-portal-banner{align-items:flex-start}
  .stApp .worker-role-badge{white-space:normal;text-align:left}
  .stApp [data-testid="stTabs"] [role="tablist"]{width:100%;gap:4px!important}
  .stApp [data-testid="stTabs"] [data-testid="stTab"]{padding:6px 9px!important}
}
@media(max-width:700px){.stApp .st-key-cta{position:static;left:auto;right:auto;bottom:auto;transform:none;width:min(100%,360px)!important;margin:18px auto 0}.stApp .st-key-cta button{width:100%}.stApp .block-container{padding-bottom:48px!important}}
@media(prefers-reduced-motion:reduce){.stApp *, .stApp *::before, .stApp *::after{scroll-behavior:auto!important;animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
"""


def inject():
    theme_css = DARK_THEME_CSS if st.session_state.get("dark_mode", False) else ""
    st.markdown(f"<style>{CSS}{theme_css}</style>", unsafe_allow_html=True)


def md(s: str):
    """Render static/escaped HTML. Strips indentation so Markdown never turns it into a code block."""
    st.markdown("".join(line.strip() for line in s.splitlines()), unsafe_allow_html=True)


def tag(text, kind=""):
    return f'<span class="tag {kind}">{h(str(text))}</span>'


def pri(p):
    return f'<span class="pd {h(p)}">{h(p)}</span>'


def status(s):
    return f'<span class="st {h(s).replace(" ", "")}">{h(s)}</span>'


def page_head(eyebrow, title, lead=""):
    md(f'<div style="padding-top:56px"><div class="eyebrow">{h(eyebrow)}</div><div class="pgh" role="heading" aria-level="1">{h(title)}</div>'
       + (f'<p class="lead">{h(lead)}</p>' if lead else "") + "</div>")


CAT_TAG = {"Electricity": "am", "Wi-Fi/Network": "b", "Water/Plumbing": "cy", "Hostel/Maintenance": "v", "Equipment": "cr", "Other": "sl"}
CAT_HEX = {"Electricity": "#D98E04", "Wi-Fi/Network": "#2F6FED", "Water/Plumbing": "#0E9EB3", "Hostel/Maintenance": "#7A5AF8", "Equipment": "#E4572E", "Other": "#64748B"}
STATUS_HEX = {"Open": "#2F6FED", "In Progress": "#D98E04", "Pending Sign-off": "#7A5AF8", "Reopened": "#E4572E", "Resolved": "#2E9E5B", "Withdrawn": "#64748B"}
PRI_HEX = {"High": "#E4572E", "Medium": "#D98E04", "Low": "#0E9EB3"}


def cat_tag(category: str) -> str:
    return tag(category, CAT_TAG.get(category, "sl"))


def sla_chip(label: str, state: str) -> str:
    return f'<span class="sla {h(state)}">{h(label)}</span>'


def kpi(label: str, value, color: str) -> str:
    return f'<div class="kpi" style="--k:{color}"><b>{h(str(value))}</b><span>{h(label)}</span></div>'


import random

_CF_COLORS = ["#F97C3C", "#2F6FED", "#7A5AF8", "#2E9E5B", "#E4572E", "#0E9EB3", "#D98E04"]
STEPS = ["Submitted", "Triaged", "In progress", "Fixed", "Closed"]


def confetti(n: int = 70) -> str:
    """CSS-only confetti (no scripts). Hidden automatically for people who prefer reduced motion."""
    r = random.Random()
    bits = "".join(f'<i style="left:{r.uniform(0, 100):.1f}%;--d:{r.uniform(0, .9):.2f}s;--t:{r.uniform(2.4, 4.2):.2f}s;--s:{r.randint(6, 11)}px;--c:{r.choice(_CF_COLORS)};'
                   f'--r:{r.randint(240, 900)}deg;--x:{r.randint(-14, 14)}vw"></i>' for _ in range(n))
    return f'<div class="cf" aria-hidden="true">{bits}</div>'


def stepper(status_value: str) -> str:
    """Where a ticket is on its journey. Reopened tickets show the step that went wrong."""
    if status_value == "Withdrawn":
        return '<ol class="stp"><li class="bad"><i></i>Withdrawn by you</li></ol>'
    done = {"Open": 2, "In Progress": 3, "Reopened": 3, "Pending Sign-off": 4, "Resolved": 5}[status_value]
    out = []
    for i, name in enumerate(STEPS):
        cls = "done" if i < done else "cur" if i == done else ""
        if status_value == "Reopened" and i == 3:
            cls, name = "bad", "Reopened"
        if status_value == "Pending Sign-off" and i == 4:
            name = "Your sign-off"
        out.append(f'<li class="{cls}"><i></i>{h(name)}</li>')
    return '<ol class="stp">' + "".join(out) + "</ol>"


def terminal(title: str, lines: list[tuple[str, str]]) -> str:
    """Dark pipeline log. Each line is (kind, html-safe text already escaped by the caller): kind in ok, warn, info, dim."""
    return f'<div class="term"><div class="ttl">{h(title)}</div>' + "".join(f'<div class="{k}">{t}</div>' for k, t in lines) + "</div>"

