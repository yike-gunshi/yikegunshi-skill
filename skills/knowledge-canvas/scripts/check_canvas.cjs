// node check_canvas.cjs output.html [--playwright /path] [--channel chrome]
// Optional: --screenshot-dir existing-dir --motion-check --pngjs /path --feishu
// Read-only checks; never writes to a host document or judges source accuracy
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{pathToFileURL}=require('url');
const {validate,extract}=require('./build_canvas.cjs');
const args=process.argv.slice(2),file=args[0];
const option=(name,fallback)=>{const i=args.indexOf(name);return i<0?fallback:args[i+1]};
async function main(){
 assert.ok(file,'请提供 HTML 路径');
 const html=fs.readFileSync(file,'utf8'),data=validate(extract(html)),bytes=Buffer.byteLength(html),checks=[],errors=[];
 if(args.includes('--feishu'))assert.ok(bytes<=500000,'超过保守 500KB 限制，请确认缩小范围或拆分，保留完整本地文件');
 assert.match(html,/<meta\s+name="use-iframe"\s+content="true"/);assert.match(html,/<meta\s+name="html-box-height-mode"\s+content="auto"/);
 const {chromium}=require(option('--playwright','playwright')),channel=option('--channel'),browser=await chromium.launch({headless:true,...(channel?{channel}:{})});
 const screenshotDir=option('--screenshot-dir');if(screenshotDir)assert.ok(fs.statSync(screenshotDir).isDirectory(),'截图目录不存在');
 const shot=async(page,name)=>{if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,name+'.png')})};
 const state=page=>page.evaluate(()=>({...window.canvasState}));
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});page.setDefaultTimeout(6000);page.on('pageerror',e=>errors.push(e.message));
  const requests=[];page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});
  await page.goto(pathToFileURL(path.resolve(file)).href);await page.waitForFunction(()=>window.canvasState?.ready);
  assert.equal((await state(page)).scale,1);assert.equal(await page.locator('[data-node]').count(),data.nodes.length);assert.equal(await page.locator('[data-doc-node]').count(),data.nodes.length);assert.deepEqual(requests,[]);checks.push('数据校验、完整节点与文档覆盖、离线自包含');
  const geometry=await page.evaluate(()=>{
   const {nodes,groups,edges,connectors=[]}=canvasAPI.data,issues=[],inside=(a,b,header=0)=>a.x>=b.x&&a.y>=b.y+header&&a.x+a.w<=b.x+b.w&&a.y+a.h<=b.y+b.h;
   for(const n of nodes){if(n.group&&!inside(n,groups.find(g=>g.id===n.group),78))issues.push(n.id+' 超出容器内容区');const texts=[...document.querySelectorAll('#node-'+n.id+' .node-title,#node-'+n.id+' .node-summary,#node-'+n.id+' .node-english')];for(const t of texts){const r=t.getBBox();if(r.x<n.x-1||r.y<n.y-1||r.x+r.width>n.x+n.w+1||r.y+r.height>n.y+n.h+1)issues.push(n.id+' 文本超出节点: '+t.textContent)}}
   for(const g of groups){if(g.parent&&!inside(g,groups.find(p=>p.id===g.parent),78))issues.push(g.id+' 超出父级内容区');for(const t of document.querySelectorAll('[data-group="'+g.id+'"] text')){const r=t.getBBox();if(r.x+r.width>g.x+g.w-8)issues.push(g.id+' 标题超宽')}}
   for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){const a=nodes[i],b=nodes[j];if(a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y)issues.push(a.id+' 与 '+b.id+' 重叠')}
   for(const e of [...edges,...connectors]){const points=e.renderPoints||e.points;for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];for(const n of nodes){if(n.id===e.from||n.id===e.to)continue;const crossed=a[0]===b[0]?a[0]>n.x+2&&a[0]<n.x+n.w-2&&Math.max(a[1],b[1])>n.y+2&&Math.min(a[1],b[1])<n.y+n.h-2:a[1]>n.y+2&&a[1]<n.y+n.h-2&&Math.max(a[0],b[0])>n.x+2&&Math.min(a[0],b[0])<n.x+n.w-2;if(crossed)issues.push(e.id+' 穿过无关节点 '+n.id)}}}
   return issues;
  });assert.deepEqual(geometry,[]);checks.push('容器层级、节点和文字边界、连线不穿无关节点');
  const renderedRoutes=await page.evaluate(()=>{
   const issues=[],data=canvasAPI.data,boxes=new Map([...data.groups,...data.nodes].map(n=>[n.id,n]));
   for(const e of [...data.edges,...(data.connectors||[])]){
    const attr=e.from?'data-edge':'data-connector',path=document.querySelector('.edge-set['+attr+'="'+e.id+'"] .edge'),points=e.renderPoints||e.points,last=points.at(-1),length=path.getTotalLength(),end=path.getPointAtLength(length);
    if(Math.hypot(end.x-last[0],end.y-last[1])>1)issues.push(e.id+' SVG 终点偏离路径');
    if(e.arrow===false)continue;
    const before=path.getPointAtLength(Math.max(0,length-4)),dx=end.x-before.x,dy=end.y-before.y,box=boxes.get(e.to);
    if(!e.renderPoints&&box){const side=Math.abs(last[0]-box.x)<2||Math.abs(last[0]-box.x-box.w)<2?'horizontal':'vertical';if(side==='horizontal'?Math.abs(dy)>.2:Math.abs(dx)>.2)issues.push(e.id+' 圆角后箭头末段不是直线')}
    const marker=document.querySelector(path.getAttribute('marker-end').replace('url(','').replace(')',''));
    if(!marker)issues.push(e.id+' 缺少箭头 marker');
    else{const tip=marker.querySelector('path').getBBox();if(Math.abs(tip.x+tip.width-marker.refX.baseVal.value)>.5)issues.push(e.id+' 箭头尖端与路径终点错位')}
   }return issues;
  });assert.deepEqual(renderedRoutes,[]);checks.push('连接边界、法向接入、终端直线、折点数量及实际 SVG 箭头');
  const contents=await page.evaluate(()=>{
   const failures=[];for(const n of canvasAPI.data.nodes){canvasAPI.show(n.id);const panel=document.querySelector('#panel-body'),doc=document.querySelector('[data-doc-node="'+n.id+'"]');if(panel.querySelector('.explanation').textContent!==doc.querySelector('.explanation').textContent)failures.push(n.id+' 说明不一致');for(const root of [panel,doc])n.samples.forEach((s,si)=>s.blocks.forEach((b,bi)=>{const pre=root.querySelector('[data-sample="'+n.id+':'+si+':'+bi+'"]');if(pre?.textContent!==b.raw)failures.push(n.id+' 原文改变')}));panel.scrollTop=1000;canvasAPI.show(n.id);if(panel.scrollTop!==0)failures.push(n.id+' 未复位滚动')}canvasAPI.hide();return failures;
  });assert.deepEqual(contents,[]);checks.push('节点与文档说明一致、全部样例原文不变、详情滚动归零');
  const aux=[...data.edges,...(data.connectors||[])].filter(e=>e.importance==='auxiliary');
  if(aux.length){const visibility=()=>page.locator('.edge-set.auxiliary').evaluateAll(els=>els.every(el=>getComputedStyle(el).display==='none'));assert.equal(await visibility(),true);const before=await state(page);await page.locator('#dependencies').click();assert.equal(await visibility(),false);assert.equal((await state(page)).scale,before.scale);assert.equal(await page.locator('[data-node]').count(),data.nodes.length);await shot(page,'dependencies');await page.locator('#dependencies').click()}
  for(const e of data.edges.filter(e=>e.relation==='dependency'&&e.importance==='primary'))assert.equal(await page.locator('[data-edge="'+e.id+'"] .edge').evaluate(el=>getComputedStyle(el.parentElement).display!=='none'&&getComputedStyle(el).visibility!=='hidden'&&el.getTotalLength()>0),true);checks.push('辅助线单独开关、核心依赖与节点常驻');
  await page.locator('#fit').click();await page.mouse.move(1,1);await shot(page,'overview');
  const node=page.locator('[data-node]').first();await node.hover();await page.waitForTimeout(220);assert.equal(await page.locator('#panel').isVisible(),false);await page.mouse.move(1,1);await page.waitForTimeout(650);assert.equal(await page.locator('#panel').isVisible(),false);
  await node.hover();await page.waitForTimeout(680);assert.equal(await page.locator('#panel').isVisible(),true);assert.ok((await page.locator('#panel').boundingBox()).width<=456);await shot(page,'detail');
  await page.locator('#pin').click();await page.mouse.move(1,1);await page.waitForTimeout(380);assert.equal((await state(page)).pinned,true);await page.keyboard.press('Escape');assert.equal(await page.locator('#panel').isVisible(),false);checks.push('600ms hover、快速划过取消、455px 弹窗、固定与 Esc');
  await node.focus();await page.keyboard.press('Enter');assert.equal((await state(page)).pinned,true);await page.keyboard.press('Escape');await page.locator('#fit').focus();await node.hover();await page.waitForTimeout(100);await page.mouse.wheel(0,90);await page.mouse.move(1,1);await page.waitForTimeout(680);assert.equal(await page.locator('#panel').isVisible(),false);checks.push('键盘节点与缩放取消待弹出');
  const sampleNode=data.nodes.find(n=>n.samples.length);if(sampleNode){await page.evaluate(id=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value=>{window.copied=value}}});canvasAPI.show(id)},sampleNode.id);await page.locator('#panel .copy').first().click();assert.equal(await page.evaluate(()=>window.copied),sampleNode.samples[0].blocks[0].raw);await page.keyboard.press('Escape');checks.push('复制保留原文（测试替身验证，宿主剪贴板权限另验）')}
  await page.locator('#readable').click();await page.locator('#zoom-in').click();assert.ok((await state(page)).scale>1);await page.locator('#readable').click();assert.equal((await state(page)).scale,1);
  const v=await page.locator('#viewport').boundingBox(),beforeDrag=await state(page);await page.mouse.move(v.x+8,v.y+v.height-8);await page.mouse.down();await page.mouse.move(v.x+60,v.y+v.height-35,{steps:8});await page.mouse.up();assert.notEqual((await state(page)).x,beforeDrag.x);
  if(data.groups.length)await page.locator('#module-select').selectOption(data.groups.at(-1).id);checks.push('缩放、100%、拖动、模块定位');
  const beforeTabs=await state(page);await page.locator('#tab-document').click();await shot(page,'document');await page.locator('#tab-canvas').click();assert.equal((await state(page)).scale,beforeTabs.scale);assert.equal((await state(page)).x,beforeTabs.x);await page.locator('#tab-canvas').focus();await page.keyboard.press('ArrowRight');assert.equal((await state(page)).view,'document');await page.locator('#tab-canvas').click();
  assert.equal(await page.locator('#tab-faq').isVisible(),Boolean(data.faq?.length||data.meta.reserveFAQ));if(data.faq?.length){await page.locator('#tab-faq').click();assert.equal(await page.locator('.faq-item').count(),data.faq.length);await shot(page,'faq');if(data.faq.some(f=>f.nodeIds?.length)){await page.locator('.faq-links button').first().click();assert.equal((await state(page)).view,'canvas');await page.waitForTimeout(60);assert.equal((await state(page)).pinned,true);await page.keyboard.press('Escape')}await page.locator('#tab-canvas').click()}checks.push('Tab 状态保持、键盘切换、FAQ 按内容展示与关联定位');
  const plan=await page.evaluate(()=>canvasAPI.motionPlan);assert.equal(await page.locator('#motion').isVisible(),Boolean(plan.length));assert.equal(await page.locator('.motion-particle').count(),plan.length);
  if(plan.length){for(const item of plan){const e=data.edges.find(e=>e.id===item.id);assert.equal(e.importance,'primary');assert.ok(['flow','loop'].includes(e.relation))}await page.locator('#motion').click();assert.equal(await page.evaluate(()=>document.querySelector('#motion-layer').animationsPaused()),true);await page.locator('#motion').click();await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(60);assert.equal(await page.evaluate(()=>document.querySelector('#motion-layer').animationsPaused()),true);await page.emulateMedia({reducedMotion:'no-preference'});await page.waitForTimeout(60);checks.push('显式主线顺序动效、暂停、减少动态偏好')}
  else checks.push('概念图默认静态，无伪执行动效');
  if(args.includes('--motion-check')&&plan.length){
   const {PNG}=require(option('--pngjs','pngjs'));await page.mouse.move(1,1);await page.evaluate(()=>{canvasAPI.hide();canvasState.x=12;canvasState.y=12;canvasAPI.zoom(.48,0,0);document.getElementById('motion-layer').pauseAnimations()});
   const item=plan.find(p=>p.end-p.start>=.85)||plan[0],take=async fraction=>{await page.evaluate(t=>document.getElementById('motion-layer').setCurrentTime(t),item.start+(item.end-item.start)*fraction);await page.waitForTimeout(70);return PNG.sync.read(await page.screenshot())};
   const a=await take(.3),b=await take(.7),boxes=await page.locator('[data-node]').evaluateAll(els=>els.map(el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}}));let moving=0,staticChanges=0;
   for(let y=0;y<a.height;y++)for(let x=0;x<a.width;x++){const p=(y*a.width+x)*4;if(a.data[p]===b.data[p]&&a.data[p+1]===b.data[p+1]&&a.data[p+2]===b.data[p+2])continue;moving++;if(boxes.some(r=>x>r.x+2&&x<r.x+r.w-2&&y>r.y+2&&y<r.y+r.h-2))staticChanges++}
   assert.ok(moving>0,'取样帧未观察到运动');assert.equal(staticChanges,0,'48% 动效改变了静态节点像素');await shot(page,'fractional-48');checks.push('48% 两帧差异：动效在移动，静态节点像素稳定');
  }
  await page.locator('#fullscreen').click();await page.waitForFunction(()=>document.fullscreenElement?.id==='canvas-app');await page.locator('#fit').click();await node.click();assert.equal(await page.locator('#panel').evaluate(el=>document.fullscreenElement.contains(el)),true);await shot(page,'fullscreen');await page.keyboard.press('Escape');await page.evaluate(()=>document.fullscreenElement&&document.exitFullscreen());
  await page.setViewportSize({width:1100,height:480});await page.waitForTimeout(60);await page.locator('#fit').click();await shot(page,'short');assert.equal(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight+1),true);
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(60);await page.locator('#fit').click();await node.click();const inside=await page.locator('#panel').evaluate(el=>{const r=el.getBoundingClientRect();return r.x>=0&&r.y>=0&&r.right<=innerWidth&&r.bottom<=innerHeight});assert.ok(inside);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await shot(page,'narrow');checks.push('全屏含详情、矮屏、390px 边界');
  async function embedded(allowed,nested=false){
   const p=await browser.newPage({viewport:{width:1440,height:1000}});p.on('pageerror',e=>errors.push(e.message));const iframe=`<iframe id="test" sandbox="allow-scripts" allow="fullscreen ${allowed?'*':"'none'"}" style="width:820px;height:940px;border:0"></iframe>`;
   await p.route('https://canvas.test/',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><body style="margin:0">'+(nested?'<iframe id="outer" allow="fullscreen *" style="width:840px;height:960px;border:0"></iframe>':iframe)}));await p.goto('https://canvas.test/');if(nested)await p.locator('#outer').evaluate((el,text)=>el.srcdoc='<!doctype html><body style="margin:0">'+text,iframe);
   const host=nested?p.frameLocator('#outer'):p;await host.locator('#test').evaluate((el,text)=>el.srcdoc=text,html);const f=host.frameLocator('#test');await f.locator('#world').evaluate(()=>{if(!canvasState.ready)throw Error('未初始化')});assert.equal(await f.locator('#viewport').evaluate(el=>el.offsetHeight),640);
   await f.locator('#fullscreen').click();if(allowed){await f.locator('#canvas-app').evaluate(()=>new Promise((resolve,reject)=>{let tries=0;const timer=setInterval(()=>{if(document.fullscreenElement){clearInterval(timer);resolve()}else if(++tries>40){clearInterval(timer);reject(Error('嵌入全屏未生效'))}},50)}));await p.waitForTimeout(100);const bounds=await f.locator('#canvas-app').evaluate(el=>{const a=el.getBoundingClientRect(),b=document.querySelector('.bottom').getBoundingClientRect(),v=document.getElementById('viewport').getBoundingClientRect();return {id:document.fullscreenElement.id,w:a.width,h:a.height,bottom:b.bottom,canvasBottom:v.bottom,toolbarTop:b.top}});assert.equal(bounds.id,'canvas-app');assert.equal(bounds.w,1440);assert.equal(bounds.h,1000);assert.ok(bounds.canvasBottom<=bounds.toolbarTop&&bounds.bottom<1000);await f.locator('#fullscreen').click();await f.locator('#viewport').evaluate(el=>new Promise((resolve,reject)=>{const until=performance.now()+3000;const wait=()=>!document.fullscreenElement&&el.offsetHeight===640?resolve():performance.now()>until?reject(Error('退出全屏未恢复嵌入高度')):requestAnimationFrame(wait);wait()}))}else assert.match(await f.locator('#display-status').innerText(),/未开放全屏/);await p.close();
  }
  await embedded(true);await embedded(true,true);await embedded(false);checks.push('640px 嵌入、嵌套全屏、退出恢复、权限受限提示');
  assert.deepEqual(errors,[]);checks.push('无运行时脚本异常');
  console.log(JSON.stringify({passed:true,bytes,nodes:data.nodes.length,edges:data.edges.length,checksCount:checks.length,checks,limits:'本地 Chromium 回归，不证明材料准确性或真实宿主渲染；剪贴板使用替身验证'},null,2));
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});
