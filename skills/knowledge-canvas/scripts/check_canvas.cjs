// 用法：node check_canvas.cjs output.html [--playwright /path/to/playwright] [--channel chrome] [--feishu] [--screenshot-dir /existing/dir]
// 只检查复用模板的交互和几何边界；不判定内容抽象正确，也不执行飞书写入
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const args=process.argv.slice(2),file=args[0];
const option=(name,fallback)=>{const i=args.indexOf(name);return i<0?fallback:args[i+1];};
if(!file){console.error('请提供 HTML 路径');process.exit(1);}
const html=fs.readFileSync(file,'utf8'),bytes=Buffer.byteLength(html),checks=[],errors=[];
if(args.includes('--feishu')&&bytes>500000){console.error('HTML 超过保守 500KB 限制，请确认缩小范围或拆分，保留本地完整文件');process.exit(1);}
assert.match(html,/<meta\s+name="use-iframe"\s+content="true"/);
assert.match(html,/<meta\s+name="html-box-height-mode"\s+content="auto"/);
const {chromium}=require(option('--playwright','playwright'));
(async()=>{
 const channel=option('--channel'),browser=await chromium.launch({headless:true,...(channel?{channel}:{})});
 const screenshotDir=option('--screenshot-dir');
 const screenshot=async(page,name)=>{if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,name+'.png')});};
 try{
  async function setup(allowed=true,nested=false){
   const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(8000);
   page.on('pageerror',e=>errors.push(e.message));
   const embed=`<iframe id="test" sandbox="allow-scripts" allow="fullscreen ${allowed?'*':"'none'"}" style="width:820px;height:900px;border:0"></iframe>`;
   await page.route('https://canvas.test/',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><body style="margin:0">'+(nested?'<iframe id="outer" allow="fullscreen *" style="width:840px;height:450px;border:0"></iframe>':embed)}));
   await page.goto('https://canvas.test/');
   if(nested)await page.locator('#outer').evaluate((el,inner)=>el.srcdoc='<!doctype html><body style="margin:0">'+inner,embed);
   const host=nested?page.frameLocator('#outer'):page;
   await host.locator('#test').evaluate((el,html)=>el.srcdoc=html,html);
   const frame=host.frameLocator('#test');await frame.locator('#world').evaluate(()=>{if(!window.canvasState?.ready)throw Error('画布未初始化');});
   const height=await frame.locator('.shell').evaluate(el=>Math.ceil(el.getBoundingClientRect().height));
   await host.locator('#test').evaluate((el,h)=>el.style.height=h+'px',height);
   return {page,host,frame,state:()=>frame.locator('body').evaluate(()=>({...window.canvasState}))};
  }
  async function enter(t){
   await t.page.bringToFront();
   await t.frame.locator('#fullscreen').scrollIntoViewIfNeeded();
   await t.page.waitForTimeout(150);
   await t.frame.locator('body').evaluate(()=>document.addEventListener('click',e=>window.lastClicked=e.target.id,{once:true,capture:true}));
   await t.frame.locator('#fullscreen').click();
   await t.frame.locator('.shell').evaluate(()=>new Promise((resolve,reject)=>{let n=0;const timer=setInterval(()=>{if(document.fullscreenElement){clearInterval(timer);resolve();}else if(++n>60){clearInterval(timer);reject(Error(JSON.stringify({error:'全屏未生效',status:document.getElementById('display-status').textContent,clicked:window.lastClicked,available:document.fullscreenEnabled})));}},50);}));
   await t.page.waitForTimeout(250);
  }
  async function layout(t){
   const b=await t.frame.locator('.shell').evaluate(el=>{const a=el.getBoundingClientRect(),v=document.getElementById('viewport').getBoundingClientRect(),b=document.querySelector('.bottom').getBoundingClientRect();return {height:a.height,width:a.width,bottom:a.bottom,canvas:v.height,canvasBottom:v.bottom,toolbarTop:b.top,toolbarBottom:b.bottom,id:document.fullscreenElement?.id};});
   const size=t.page.viewportSize();assert.equal(b.id,'canvas-app');assert.equal(b.height,size.height);assert.equal(b.width,size.width);
   assert.ok(b.canvas>size.height-260,JSON.stringify(b));assert.ok(b.canvasBottom<=b.toolbarTop,JSON.stringify(b));
   assert.ok(b.toolbarBottom<=b.bottom-8&&b.toolbarBottom>=b.bottom-40,JSON.stringify(b));
  }
  const t=await setup();
  assert.equal((await t.state()).scale,1);assert.equal(await t.frame.locator('#viewport').evaluate(el=>el.offsetHeight),640);
  assert.equal(await t.frame.locator('#status,#runtime').count(),0);checks.push('默认 100% 与 640px 正文画布','无可见调试计数或运行标记');
  await t.frame.locator('#fit').click();const node=t.frame.locator('[data-node]').first();
  await node.hover();await t.page.waitForTimeout(250);assert.equal(await t.frame.locator('#panel').isVisible(),false);
  await t.page.mouse.move(2,2,{steps:8});await t.page.waitForTimeout(650);assert.equal(await t.frame.locator('#panel').isVisible(),false);
  await node.hover();await t.page.waitForTimeout(680);assert.equal(await t.frame.locator('#panel').isVisible(),true);
  assert.ok(await t.frame.locator('[data-io="input"]').count());assert.ok(await t.frame.locator('[data-io="output"]').count());
  checks.push('延迟 hover 和快速划过取消','详情同时有输入和输出');
  await node.click();await t.page.mouse.move(2,2,{steps:8});await t.page.waitForTimeout(350);assert.equal((await t.state()).pinned,true);
  await t.page.keyboard.press('Escape');assert.equal(await t.frame.locator('#panel').isVisible(),false);checks.push('点击固定与 Esc');
  await t.frame.locator('#readable').click();await t.frame.locator('#zoom-in').click();assert.ok((await t.state()).scale>1);
  await t.frame.locator('#readable').click();assert.equal((await t.state()).scale,1);
  const v=await t.frame.locator('#viewport').boundingBox(),before=await t.state();
  await t.page.mouse.move(v.x+8,v.y+v.height-8);await t.page.mouse.down();await t.page.mouse.move(v.x+65,v.y+v.height-35,{steps:8});await t.page.mouse.up();
  assert.notEqual((await t.state()).x,before.x);checks.push('缩放、重置和平移');
  const options=await t.frame.locator('#module-select option').evaluateAll(els=>els.filter(el=>el.value).map(el=>el.value));
  assert.ok(options.length);await t.frame.locator('#module-select').selectOption(options[options.length-1]);checks.push('模块定位');
  await t.frame.locator('#readable').click();await enter(t);await layout(t);await screenshot(t.page,'canvas-fullscreen');
  await t.frame.locator('#fit').click();await node.click();assert.equal(await t.frame.locator('#panel').evaluate(el=>document.fullscreenElement.contains(el)),true);
  const inside=()=>t.frame.locator('#panel').evaluate(el=>{const r=el.getBoundingClientRect(),a=document.querySelector('.shell').getBoundingClientRect();return r.left>=a.left&&r.top>=a.top&&r.right<=a.right&&r.bottom<=a.bottom;});
  assert.ok(await inside());await screenshot(t.page,'canvas-detail');await t.frame.locator('#close').click();
  checks.push('全屏占满剩余空间且底栏不遮挡','全屏浮层属于应用容器且边界正常');
  await t.page.setViewportSize({width:1100,height:480});await t.page.waitForTimeout(100);await layout(t);await screenshot(t.page,'canvas-short');
  await t.frame.locator('#fullscreen').click();await t.page.waitForTimeout(150);assert.equal(await t.frame.locator('#viewport').evaluate(el=>el.offsetHeight),640);checks.push('矮屏全屏与退出恢复');
  await t.page.setViewportSize({width:1100,height:1000});await t.host.locator('#test').evaluate(el=>el.style.width='390px');
  const height=await t.frame.locator('.shell').evaluate(el=>el.offsetHeight);await t.host.locator('#test').evaluate((el,h)=>el.style.height=h+'px',height);
  await t.frame.locator('#fit').click();await node.click();assert.ok(await inside());assert.equal(await t.frame.locator('html').evaluate(el=>el.scrollWidth<=innerWidth),true);await screenshot(t.page,'canvas-narrow');checks.push('390px 正文与详情无溢出');
  const nested=await setup(true,true);await enter(nested);await layout(nested);checks.push('嵌套 iframe 全屏');
  const denied=await setup(false);await denied.frame.locator('#fullscreen').click();assert.match(await denied.frame.locator('#display-status').innerText(),/未开放全屏/);checks.push('全屏受限有说明');
  assert.deepEqual(errors,[]);checks.push('无脚本异常');
  console.log(JSON.stringify({passed:true,bytes,feishuSizeEligible:bytes<=500000,checksCount:checks.length,checks,limits:'仅本地模板交互验证，未验证内容准确性或飞书真实客户端'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});


