"""One architecture illustration, with screen and print layouts from shared content.

The labels describe contracts.py, engine.py, execution.py and publication.py.
Drawing primitives follow Matplotlib's FancyBboxPatch and FancyArrowPatch APIs:
https://matplotlib.org/stable/api/_as_gen/matplotlib.patches.FancyBboxPatch.html
https://matplotlib.org/stable/api/_as_gen/matplotlib.patches.FancyArrowPatch.html
"""
from html import escape
from importlib.resources import files
from pathlib import Path

from .contracts import PHASES


INK, MUTED, LINE, BG = '#142d40', '#506778', '#cddce5', '#f2f6f8'
TEAL, BLUE, AMBER, VIOLET = '#087f80', '#315bb5', '#a56317', '#7551a5'
PHASE_DETAILS = {
    'research': ('Scope + research', 'Question + success criteria\nLiterature, code + licenses\nSources + open questions', 'Define the problem', TEAL),
    'preregister': ('Preregister', 'Hypothesis or exploration\nMetrics, controls + analysis\nFreeze the protocol in Git', 'Before relevant results', TEAL),
    'core': ('Implement +\npublish core', 'Working code + checks\nREADME + reproduction\nPush before any training', 'CORE PUBLICATION GATE', BLUE),
    'pilot': ('Pilot + publish', 'Smallest useful experiment\nPredictions + checkpoint\nPublish preliminary findings', 'Before sensitivity runs', BLUE),
    'experiments': ('Comparative\nexperiments', 'Baselines, controls + ablations\nSeeds + sensitivity checks\nKeep negative findings too', 'Registered comparisons', AMBER),
    'analysis': ('Analyze + distill', 'Statistics, intervals + plots\nClaims linked to evidence\nReports, paper + explorer', 'Numbers from saved results', VIOLET),
    'review': ('Review + repair', 'Code + methodology review\nCitations + reproducibility\nRepair concrete failures', 'Reopen missing evidence', VIOLET),
    'publish': ('Publish + decide', 'Merge PRs + verify artifacts\nGitHub Pages + model bundles\nStop or begin a new cycle', 'Preserve the full history', TEAL),
}
RUNTIME = [
    ('Build context', 'Original policy + task\nPhase objective + findings\nPrior evidence + corrections', 'policy.py / phases.py'),
    ('Invoke one CLI', 'Claude Code OR Codex\nOne selected model per run\nSearch / edit / execute', 'adapters.py / execution.py'),
    ('Verify evidence', 'Structured result + artifacts\nProtocol, hashes + metrics\nClaims + source records', 'contracts.py / science.py'),
    ('Finalize progress', 'Persist the accepted handoff\nPublish with saved receipts\nRecord phase completion', 'engine.py / publication.py'),
]
MEMORY = [
    ('SQLite state', 'Phase attempts + cycle ownership\nCall counts + active elapsed time\nPending handoffs + receipts', 'state.py', BLUE),
    ('Research artifacts', 'Protocols, predictions + checkpoints\nSources, claims + decision history\nRaw timestamped logs stay local', 'cycles/ + ignored .eureka/', TEAL),
    ('Published evidence', 'GitHub: code, reports + merged PRs\nPages: interactive results explorer\nHugging Face: checkpoint collection', 'Reproducible, sanitized artifacts', VIOLET),
]


class Diagram:
    """Use a top-left coordinate grid so each layout reads like the final figure."""
    def __init__(self, width, height):
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
        from matplotlib.path import Path as PlotPath
        self.plt, self.Arrow, self.Box, self.Path = plt, FancyArrowPatch, FancyBboxPatch, PlotPath
        self.width,self.height = width,height
        self.fig = plt.figure(figsize=(width/100,height/100),facecolor=BG)
        self.ax = self.fig.add_axes((0,0,1,1),xlim=(0,width),ylim=(height,0))
        self.ax.axis('off')

    def text(self, x, y, value, size=13, color=INK, weight='normal', **kwargs):
        kwargs.setdefault('linespacing',1.5)
        self.ax.text(x,y,value,fontsize=size,color=color,fontweight=weight,
                     va='top',**kwargs)

    def box(self, x, y, width, height, fill='white', edge=LINE, radius=15):
        self.ax.add_patch(self.Box((x,y),width,height,boxstyle=f'round,pad=0,rounding_size={radius}',
                                  facecolor=fill,edgecolor=edge,linewidth=1))

    def arrow(self, points, color=BLUE, dashed=False):
        path = self.Path(points,[self.Path.MOVETO]+[self.Path.LINETO]*(len(points)-1))
        self.ax.add_patch(self.Arrow(path=path,arrowstyle='-|>',mutation_scale=14,
                                   linewidth=1.5,color=color,linestyle=(0,(4,3)) if dashed else '-'))

    def header(self, title, subtitle):
        self.text(54,34,'AUTO EUREKA SCIENTIST  /  SYSTEM ARCHITECTURE',11,TEAL,'bold')
        self.text(54,73,title,29,INK,'bold')
        self.text(54,127,subtitle,13,MUTED)

    def phase(self, x, y, width, height, index):
        key = PHASES[index]
        title,body,note,color = PHASE_DETAILS[key]
        self.box(x,y,width,height)
        self.box(x+18,y+16,34,27,color,color,8)
        self.text(x+35,y+19,f'{index+1:02}',10,'white','bold',ha='center')
        self.text(x+64,y+21,key.upper(),9.5,color,'bold')
        self.text(x+20,y+57,title,17,INK,'bold',linespacing=1.15)
        self.text(x+20,y+119,body,12.1,MUTED)
        self.text(x+20,y+height-24,note,9.5,color,'bold')

    def component(self, x, y, width, height, title, body, note, color=BLUE):
        self.box(x,y,width,height)
        self.ax.plot([x+20,x+49],[y+22,y+22],color=color,linewidth=3,solid_capstyle='round')
        self.text(x+20,y+38,title,17,INK,'bold')
        self.text(x+20,y+77,body,12,MUTED)
        self.text(x+20,y+height-24,note,9,color,'bold')

    def save(self, destination):
        """Export stable vector and raster assets; no empirical values are authored here."""
        self.fig.savefig(destination.with_suffix('.png'),dpi=180)
        self.fig.savefig(destination.with_suffix('.svg'),metadata={'Date':None,
            'Title':'Auto Eureka Scientist architecture',
            'Description':'Eight research phases, selected coding CLI, evidence verification, durable state and publication.'})
        self.plt.close(self.fig)


def phase_grid(drawing, *, compact=False):
    """Numbered snake routing keeps arrows out of card labels in both orientations."""
    columns = 2 if compact else 4
    left,top,gap,width,height = (54,182,38,407,218) if compact else (54,330,24,312,224)
    vertical_gap = 32 if compact else 42
    positions = []
    for index in range(len(PHASES)):
        row,column = divmod(index,columns)
        if row%2:
            column = columns-1-column
        x,y = left+column*(width+gap),top+row*(height+vertical_gap)
        positions.append((x,y))
        drawing.phase(x,y,width,height,index)
    for (x,y),(next_x,next_y) in zip(positions,positions[1:]):
        if next_y==y:
            direction = 1 if next_x>x else -1
            drawing.arrow([(x+(width if direction>0 else 0),y+height/2),
                           (next_x+(0 if direction>0 else width),next_y+height/2)])
        else:
            drawing.arrow([(x+width/2,y+height),(next_x+width/2,next_y)])
    # This is an optional cycle boundary, not a claim that every run repeats.
    x,y = positions[-1]
    drawing.arrow([(x,y+height/2),(26,y+height/2),(26,top-18),(left+width/2,top-18),
                   (left+width/2,top)],TEAL,True)


def overview(destination):
    drawing = Diagram(1440,1600)
    drawing.header('From question to verifiable evidence',
                   'One selected provider and model. Fresh contexts. A research history that survives interruptions.')
    drawing.box(54,188,1320,74,INK,INK)
    drawing.text(76,205,'INPUTS',10,'#8bddd5','bold')
    drawing.text(176,201,'Task + unchanged policy + project + backend/model + stopping mode + explicit limits',14,'white')
    drawing.text(54,291,'01 / THE RESEARCH CYCLE',12,TEAL,'bold')
    phase_grid(drawing)
    drawing.text(54,852,'Dashed return: another cycle when allowed. Review or distillation can reopen earlier work.',12,TEAL)
    drawing.text(54,880,'Neel Nanda’s stages recur throughout: ideation → exploration → understanding → distillation.',12,MUTED)
    drawing.text(54,938,'02 / THE SAME EXECUTION LOOP AT EVERY PHASE',12,BLUE,'bold')
    for i,item in enumerate(RUNTIME):
        drawing.component(54+i*336,982,312,184,*item)
        if i<3:
            drawing.arrow([(366+i*336,1074),(390+i*336,1074)])
    drawing.arrow([(882,1166),(882,1216),(210,1216),(210,1166)],AMBER,True)
    drawing.text(316,1181,'Failed checks: targeted repair with the same backend',11,AMBER)
    drawing.text(54,1263,'03 / DURABLE MEMORY + PUBLICATION',12,VIOLET,'bold')
    for i,item in enumerate(MEMORY):
        drawing.component(54+i*448,1305,424,184,*item)
    drawing.text(54,1515,'STOP / RESUME',10,TEAL,'bold')
    drawing.text(216,1511,'Cycle / continuous / budget. Stop or limit → incomplete work saved; resume retains spent calls + time.',12,INK)
    drawing.text(216,1545,'Revised hypotheses use a new protocol and cycle. Earlier observations and negative results remain.',11,MUTED)
    drawing.save(destination)


def print_phases(destination):
    drawing = Diagram(960,1265)
    drawing.header('The research cycle','Publication gates separate planning, pilot evidence and comparisons.')
    phase_grid(drawing,compact=True)
    drawing.text(54,1165,'REVISIT WITHOUT REWRITING HISTORY',11,TEAL,'bold')
    drawing.text(54,1195,'Distillation or review can reopen missing evidence. Changed hypotheses after results\nrequire a new cycle and protocol; the earlier observations remain recorded.',12,MUTED)
    drawing.save(destination)


def print_runtime(destination):
    drawing = Diagram(960,1100)
    drawing.header('Execution, memory + recovery','The controller repeats this loop for each phase and every repair attempt.')
    positions = [(54,193),(499,193),(499,418),(54,418)]
    for position,item in zip(positions,RUNTIME):
        drawing.component(*position,407,190,*item)
    drawing.arrow([(461,288),(499,288)])
    drawing.arrow([(702,383),(702,418)])
    drawing.arrow([(499,513),(461,513)])
    drawing.arrow([(702,608),(702,655),(26,655),(26,288),(54,288)],AMBER,True)
    drawing.text(54,680,'Recovery keeps the evidence',19,INK,'bold')
    drawing.text(54,722,'SQLite retains attempts, budgets, cycle ownership and pending handoffs.\nFiles retain protocols, predictions, checkpoints, claims and decision histories.\nStreaming stdout/stderr and complete prompts stay in local timestamped logs.',13,MUTED)
    drawing.box(54,823,852,104,INK,INK)
    drawing.text(77,842,'PUBLICATION + RESUME SHARE RECEIPTS',11,'#8bddd5','bold')
    drawing.text(77,873,'GitHub + merged PRs   /   GitHub Pages   /   Hugging Face collections',13,'white')
    drawing.text(54,958,'Bounded recovery',14,TEAL,'bold')
    drawing.text(54,990,'Up to two targeted repairs and two transient retries per phase execution.\nPublication recovery reuses an accepted handoff without another model call.\nStop / limits / interruption leave incomplete work available for resume.',12,MUTED)
    drawing.save(destination)


def render_architecture(directory: Path):
    """Build all views together so README, paper and website cannot drift apart."""
    import matplotlib
    matplotlib.use('Agg')
    if tuple(PHASE_DETAILS)!=PHASES:
        raise ValueError('Architecture labels must cover the implemented phases in order')
    directory.mkdir(parents=True,exist_ok=True)
    with matplotlib.rc_context({'font.family':'DejaVu Sans','svg.hashsalt':'auto-eureka-architecture'}):
        overview(directory/'architecture')
        print_phases(directory/'architecture-phases')
        print_runtime(directory/'architecture-runtime')


def architecture_panel():
    """Accessible text and an optional zoomable vector view share the figure labels."""
    items = ''.join(f'<li><strong>{escape(title.replace(chr(10)," "))}.</strong> '
                    f'{escape(body.replace(chr(10),"; "))}.</li>'
                    for title,body,_,_ in PHASE_DETAILS.values())
    return files('auto_eureka_scientist').joinpath('resources/architecture-panel.html').read_text(encoding='utf-8').replace('<!-- PHASE_DESCRIPTIONS -->',items)
