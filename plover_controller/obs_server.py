import json
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler


def _sse_stream(wfile, server_ref):
    last_version = 0
    with server_ref._condition:
        state = server_ref._state
        version = server_ref._version
    if state:
        wfile.write(
            f"data: {json.dumps(state, separators=(',', ':'))}\n\n".encode())
        wfile.flush()
        last_version = version
    try:
        while not server_ref._stopping:
            with server_ref._condition:
                server_ref._condition.wait_for(
                    lambda: server_ref._version > last_version
                    or server_ref._stopping,
                    timeout=15)
                state = server_ref._state
                version = server_ref._version
            if version > last_version:
                last_version = version
                wfile.write(
                    f"data: {json.dumps(state, separators=(',', ':'))}\n\n"
                    .encode())
                wfile.flush()
            else:
                wfile.write(b": keepalive\n\n")
                wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass


def _sse_headers(handler):
    handler.send_response(200)
    handler.send_header('Content-Type', 'text/event-stream')
    handler.send_header('Cache-Control', 'no-cache')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.end_headers()


class _BaseStateServer:
    def __init__(self, port, handler_class):
        self._state = {}
        self._condition = threading.Condition()
        self._version = 0
        self._stopping = False
        self._httpd = ThreadingHTTPServer(('127.0.0.1', port), handler_class)
        self._httpd.allow_reuse_address = True
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stopping = True
        with self._condition:
            self._condition.notify_all()
        self._httpd.shutdown()

    def update_state(self, state):
        with self._condition:
            self._state = state
            self._version += 1
            self._condition.notify_all()


class OBSStateServer(_BaseStateServer):
    def __init__(self, port=8079):
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    body = _HTML_PAGE.encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == '/events':
                    _sse_headers(self)
                    _sse_stream(self.wfile, server_ref)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                pass

        super().__init__(port, Handler)


class APIStateServer(_BaseStateServer):
    def __init__(self, port=8080):
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/events':
                    _sse_headers(self)
                    _sse_stream(self.wfile, server_ref)
                elif self.path == '/state':
                    with server_ref._condition:
                        state = server_ref._state
                    body = json.dumps(state, separators=(',', ':')).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                pass

        super().__init__(port, Handler)


_HTML_PAGE = r'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
html,body{margin:0;overflow:hidden;width:100%;height:100%;background:transparent}
canvas{width:100%;height:100%;display:block}
</style></head><body>
<canvas id="c"></canvas>
<script>
const REF_W=1000,REF_H=580,SR=52;
const SP={left:[280,190],right:[640,365]};
const DCX=280,DCY=367,DS=18;
const IL={guide:'◉',back:'◁',start:'▷',misc1:'☆'};
const CC={
  body:'rgb(40,40,44)',bs:'rgb(65,65,70)',
  off:'rgb(58,58,64)',os:'rgb(85,85,92)',
  on:'#fff',ons:'rgb(220,220,220)',
  lb:'rgb(170,170,175)',lba:'rgb(25,25,25)',
  sbg:'rgb(30,30,34)',db:'rgb(48,48,54)',dbs:'rgb(55,55,60)',
  sl:'rgb(140,140,145)'
};
const F={
  y:['c','Y',718,162,26],x:['c','X',660,220,26],
  b:['c','B',776,220,26],a:['c','A',718,278,26],
  dpadu:['d',null,261,316,38,51],dpadd:['d',null,261,367,38,51],
  dpadl:['d',null,229,348,51,38],dpadr:['d',null,280,348,51,38],
  leftshoulder:['r','LB',178,68,185,34,12],
  rightshoulder:['r','RB',638,68,185,34,12],
  lefttrigger:['r','LT',200,22,142,40,10],
  righttrigger:['r','RT',658,22,142,40,10],
  guide:['c',null,500,170,20],back:['c',null,418,192,14],
  start:['c',null,582,192,14],misc1:['c',null,500,222,12],
  leftstick:['s','LS',280,190,52],rightstick:['s','RS',640,365,52],
  touchpad:['r','TP',452,250,96,42,14]
};
const B={
  lefttrigger:['r','LT',200,22,142,52,10],
  righttrigger:['r','RT',658,22,142,52,10],
  paddle1:['r','P1',655,240,55,100,14],paddle2:['r','P2',720,270,55,100,14],
  paddle3:['r','P3',225,270,55,100,14],paddle4:['r','P4',290,240,55,100,14]
};

const BP=new Path2D();
BP.moveTo(190,95);BP.bezierCurveTo(230,42,380,22,500,22);
BP.bezierCurveTo(620,22,770,42,810,95);BP.bezierCurveTo(845,140,858,210,852,270);
BP.lineTo(838,370);BP.bezierCurveTo(832,420,808,480,755,518);
BP.bezierCurveTo(715,545,678,540,648,508);BP.bezierCurveTo(618,472,592,415,562,385);
BP.bezierCurveTo(542,365,458,365,438,385);BP.bezierCurveTo(408,415,382,472,352,508);
BP.bezierCurveTo(322,540,285,545,245,518);BP.bezierCurveTo(192,480,168,420,162,370);
BP.lineTo(148,270);BP.bezierCurveTo(142,210,155,140,190,95);BP.closePath();

let S={pressed:[],stickAxes:{},triggerValues:{},activeSegments:{},
  chromaColor:'#00b140',layoutMode:'horizontal',showBack:true,
  stenoLabels:{},sticks:{},triggers:{}};

const cv=document.getElementById('c'),cx=cv.getContext('2d');
const es=new EventSource('/events');
es.onmessage=e=>{S=JSON.parse(e.data);draw()};

function rsz(){
  cv.width=innerWidth*devicePixelRatio;
  cv.height=innerHeight*devicePixelRatio;
  draw();
}
addEventListener('resize',rsz);rsz();

function xform(r){
  const p=8,ix=r.x+p,iy=r.y+p,iw=r.w-p*2,ih=r.h-p*2;
  const sc=Math.min(iw/REF_W,ih/REF_H);
  const sw=REF_W*sc,sh=REF_H*sc;
  cx.translate(ix+(iw-sw)/2,iy+(ih-sh)/2);cx.scale(sc,sc);
}

function body(){
  cx.lineWidth=3;cx.strokeStyle=CC.bs;cx.fillStyle=CC.body;
  cx.fill(BP);cx.stroke(BP);
}

function btn(el,act,steno,icon){
  const sh=el[0],lb=el[1];
  cx.lineWidth=1.8;
  cx.strokeStyle=act?CC.ons:CC.os;cx.fillStyle=act?CC.on:CC.off;
  if(sh==='c'){
    const[,,ex,ey,er]=el;
    cx.beginPath();cx.arc(ex,ey,er,0,Math.PI*2);cx.fill();cx.stroke();
    txt(ex,ey,lb,steno,icon,act,er*2);
  }else if(sh==='r'){
    const[,,ex,ey,ew,eh,ec]=el;
    cx.beginPath();cx.roundRect(ex,ey,ew,eh,ec);cx.fill();cx.stroke();
    txt(ex+ew/2,ey+eh/2,lb,steno,icon,act,Math.min(ew,eh));
  }
}

function stickBase(el,act){
  const[,,ex,ey,er]=el;
  cx.lineWidth=1.5;cx.strokeStyle=CC.os;cx.fillStyle=CC.sbg;
  cx.beginPath();cx.arc(ex,ey,er,0,Math.PI*2);cx.fill();cx.stroke();
  if(act){cx.lineWidth=3;cx.strokeStyle=CC.on;
    cx.beginPath();cx.arc(ex,ey,er+4,0,Math.PI*2);cx.stroke();}
}

function dpadBase(){
  const aw=38,ah=42;
  cx.fillStyle=CC.db;
  cx.beginPath();cx.roundRect(DCX-aw/2,DCY-ah-DS/2,aw,ah*2+DS,6);cx.fill();
  cx.beginPath();cx.roundRect(DCX-ah-DS/2,DCY-aw/2,ah*2+DS,aw,6);cx.fill();
}

function dpadArm(el,act){
  if(!act)return;
  const[,,ex,ey,ew,eh]=el;
  cx.fillStyle=CC.on;cx.beginPath();cx.roundRect(ex,ey,ew,eh,6);cx.fill();
}

function stickSegs(){
  for(const[sn,st]of Object.entries(S.sticks||{})){
    const pos=SP[sn];if(!pos)continue;
    const[px,py]=pos,n=st.segments.length,ad=(S.activeSegments||{})[sn];
    for(let i=0;i<n;i++){
      const sd=st.segments[i],ia=sd===ad;
      const as=st.offset+i*360/n,sp=360/n;
      if(ia){
        const r=SR-4,s1=as*Math.PI/180,s2=(as+sp)*Math.PI/180;
        cx.beginPath();cx.moveTo(px,py);cx.arc(px,py,r,s1,s2);cx.closePath();
        cx.fillStyle='rgba(255,255,255,0.706)';cx.fill();
      }
      const sl=(S.stenoLabels||{})[sn+sd];
      if(sl){
        const ma=(as+sp/2)*Math.PI/180,lr=SR*0.6;
        cx.fillStyle=ia?CC.lba:CC.sl;
        cx.font='bold 12px sans-serif';cx.textAlign='center';cx.textBaseline='middle';
        cx.fillText(sl,px+lr*Math.cos(ma),py+lr*Math.sin(ma));
      }
    }
  }
}

function stickInd(){
  for(const[sn,st]of Object.entries(S.sticks||{})){
    const pos=SP[sn];if(!pos)continue;
    const[px,py]=pos;
    const lr=(S.stickAxes||{})[st.xAxis]||0,ud=(S.stickAxes||{})[st.yAxis]||0;
    const r=SR-6;
    cx.lineWidth=1.5;cx.strokeStyle='rgba(200,200,200,0.706)';
    cx.fillStyle='rgba(230,230,230,0.863)';
    cx.beginPath();cx.arc(px+lr*r,py+ud*r,9,0,Math.PI*2);cx.fill();cx.stroke();
  }
}

function trigFill(side,els){
  for(const[,renamed]of Object.entries(S.triggers||{})){
    const v=(S.triggerValues||{})[renamed]||0;
    if(v<=0.01)continue;
    if(side==='left'&&!renamed.startsWith('l'))continue;
    if(side==='right'&&!renamed.startsWith('r'))continue;
    const el=els[side+'trigger'];if(!el)continue;
    const[,,ex,ey,ew,eh,ec]=el,fw=ew*Math.min(v,1);
    cx.save();cx.beginPath();cx.roundRect(ex,ey,ew,eh,ec);cx.clip();
    cx.fillStyle='rgba(255,255,255,0.549)';cx.fillRect(ex,ey,fw,eh);cx.restore();
  }
}

function txt(x,y,lb,steno,icon,act,sz){
  const d=steno||icon||lb;if(!d)return;
  cx.fillStyle=act?CC.lba:CC.lb;
  const fs=steno?Math.max(8,Math.min(18,sz*0.35|0)):Math.max(8,Math.min(21,sz*0.4|0));
  cx.font='bold '+fs+'px sans-serif';cx.textAlign='center';cx.textBaseline='middle';
  cx.fillText(d,x,y);
}

function drawView(r,view){
  cx.save();xform(r);body();
  const pr=new Set(S.pressed||[]);
  if(view==='front'){
    dpadBase();
    for(const[nm,el]of Object.entries(F)){
      const act=pr.has(nm),sh=el[0];
      if(sh==='s')stickBase(el,act);
      else if(sh==='d')dpadArm(el,act);
      else btn(el,act,(S.stenoLabels||{})[nm],IL[nm]);
    }
    stickSegs();stickInd();trigFill('left',F);trigFill('right',F);
  }else{
    for(const[nm,el]of Object.entries(B)){
      if(nm==='lefttrigger'||nm==='righttrigger')
        btn(el,false,(S.stenoLabels||{})[nm]);
      else btn(el,pr.has(nm),(S.stenoLabels||{})[nm]);
    }
    trigFill('left',B);trigFill('right',B);
  }
  cx.restore();
}

function draw(){
  const w=cv.width,h=cv.height;
  cx.clearRect(0,0,w,h);
  cx.fillStyle=S.chromaColor||'#00b140';cx.fillRect(0,0,w,h);
  let fr,br;
  if(!S.showBack){fr={x:0,y:0,w,h}}
  else if(S.layoutMode==='horizontal'){
    fr={x:0,y:0,w:w/2,h};br={x:w/2,y:0,w:w/2,h};
  }else{fr={x:0,y:0,w,h:h/2};br={x:0,y:h/2,w,h:h/2}}
  drawView(fr,'front');
  if(S.showBack&&br)drawView(br,'back');
}
</script></body></html>'''
