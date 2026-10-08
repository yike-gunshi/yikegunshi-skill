// node build_canvas.cjs material.json output.html [--overwrite]
// Only local HTML generation; no installation, publication, or network requests
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {auditRoute}=require('./route_geometry.cjs');
const DATA_TAG=/<script type="application\/json" id="canvas-data">([\s\S]*?)<\/script>/;
const templatePath=path.join(__dirname,'../assets/canvas-template.html');
function validate(d){
 const ok=(v,m)=>assert.ok(v,m),str=(v,p)=>ok(typeof v==='string',p+' 必须是文本');
 const one=(v,values,p)=>ok(values.includes(v),p+' 不在允许值中');
 const num=(v,p)=>ok(Number.isFinite(v),p+' 必须是有限数');
 const array=(v,p)=>ok(Array.isArray(v),p+' 必须是数组');
 const ids=(items,p)=>{array(items,p);const found=new Set();for(const item of items){ok(item&&typeof item==='object',p+' 必须包含对象');str(item.id,p+'.id');ok(/^[a-z][a-z0-9_-]*$/.test(item.id),p+' ID 格式错误');ok(!found.has(item.id),p+' 重复 ID: '+item.id);found.add(item.id)}return found};
 const list=(items,p)=>{array(items,p);for(const item of items){if(typeof item==='string')continue;ok(item&&typeof item==='object',p+' 列表项错误');str(item.text,p+'.text');if(item.children!==undefined)list(item.children,p+'.children')}};
 const explanation=(rows,p)=>{array(rows,p);ok(rows.length,p+' 不能为空');for(const row of rows){str(row.label,p+'.label');if(Array.isArray(row.body))list(row.body,p+'.body');else str(row.body,p+'.body')}};
 const box=(b,p)=>{['x','y','w','h'].forEach(k=>num(b[k],p+'.'+k));ok(b.w>0&&b.h>0,p+' 宽高必须为正');ok(b.x>=0&&b.y>=0&&b.x+b.w<=d.width&&b.y+b.h<=d.height,p+' 超出画布');str(b.title,p+'.title');str(b.summary,p+'.summary')};
 const points=(value,p)=>{array(value,p);ok(value.length>=2,p+' 至少两个点');for(const [i,pair] of value.entries()){ok(Array.isArray(pair)&&pair.length===2,p+' 必须是坐标对');pair.forEach(v=>num(v,p));if(i){const prev=value[i-1];ok(prev[0]===pair[0]||prev[1]===pair[1],p+' 必须是正交折线')}}};
 ok(d&&typeof d==='object','数据必须是对象');ok(d.meta,'缺少 meta');str(d.meta.title,'meta.title');one(d.meta.mode,['process','concept','mixed'],'meta.mode');['subtitle','version','canvasLabel'].forEach(k=>{if(d.meta[k]!==undefined)str(d.meta[k],'meta.'+k)});if(d.meta.reserveFAQ!==undefined)ok(typeof d.meta.reserveFAQ==='boolean','reserveFAQ 必须是布尔值');
 num(d.width,'width');num(d.height,'height');ok(d.width>0&&d.height>0,'画布尺寸必须为正');
 const groupIds=ids(d.groups,'groups'),nodeIds=ids(d.nodes,'nodes'),edgeIds=ids(d.edges,'edges'),groupMap=new Map(d.groups.map(g=>[g.id,g]));ok(d.nodes.length,'nodes 不能为空');
 for(const g of d.groups){box(g,g.id);one(g.color,['cyan','green','violet','amber','slate'],g.id+'.color');if(g.parent)ok(groupIds.has(g.parent),g.id+' 的 parent 不存在');const seen=new Set([g.id]);let parent=g.parent;while(parent){ok(!seen.has(parent),'分组存在层级环');seen.add(parent);ok(groupMap.has(parent),'分组引用不存在');parent=groupMap.get(parent).parent}}
 for(const n of d.nodes){ok(!groupIds.has(n.id),'node 和 group ID 不能重名');box(n,n.id);if(n.group)ok(groupIds.has(n.group),n.id+' 的 group 不存在');one(n.shape,['process','decision','document','database','text'],n.id+'.shape');if(n.english!==undefined)str(n.english,n.id+'.english');if(n.status){one(n.status.kind,['conditional','disabled','default-off','unverified'],n.id+'.status');str(n.status.label,n.id+'.status.label')}explanation(n.explanation,n.id+'.explanation');array(n.samples,n.id+'.samples');for(const sample of n.samples){['title','type','source'].forEach(k=>str(sample[k],n.id+'.sample.'+k));array(sample.blocks,n.id+'.blocks');ok(sample.blocks.length,n.id+' 样例块不能为空');for(const b of sample.blocks){str(b.label,n.id+'.block.label');str(b.raw,n.id+'.block.raw');one(b.format,['json','text','code','markdown','quote','math'],n.id+'.block.format');if(b.format==='json')try{JSON.parse(b.raw)}catch{throw Error(n.id+' 的原文 JSON 语法错误')}}}if(n.sources!==undefined){array(n.sources,n.id+'.sources');n.sources.forEach(s=>str(s,n.id+'.source'))}}
 const relation=e=>{one(e.relation,['flow','data','dependency','composition','condition','loop','reference'],e.id+'.relation');one(e.importance,['primary','secondary','auxiliary'],e.id+'.importance');points(e.points,e.id+'.points');if(e.arrow!==undefined)ok(typeof e.arrow==='boolean',e.id+'.arrow 必须是布尔值');if(e.label!==undefined){str(e.label,e.id+'.label');ok(Array.isArray(e.labelAt)&&e.labelAt.length===2,e.id+' 标签需要 labelAt');e.labelAt.forEach(v=>num(v,e.id+'.labelAt'))}};
 for(const e of d.edges){ok(nodeIds.has(e.from)||groupIds.has(e.from),e.id+' from 不存在');ok(nodeIds.has(e.to)||groupIds.has(e.to),e.id+' to 不存在');relation(e);if(e.renderPoints)points(e.renderPoints,e.id+'.renderPoints')}
 if(d.connectors!==undefined){ids(d.connectors,'connectors');d.connectors.forEach(relation)}
 if(d.motion!==undefined){array(d.motion.steps,'motion.steps');for(const step of d.motion.steps){array(step,'motion step');ok(step.length,'动效步骤不能为空');ok(new Set(step).size===step.length,'同一步骤不能重复一条边');for(const id of step){ok(edgeIds.has(id),'动效引用不存在: '+id);const e=d.edges.find(e=>e.id===id);ok(e.importance==='primary'&&['flow','loop'].includes(e.relation),'动效仅适用于主流程或主循环: '+id);ok(!e.renderPoints,'汇合支线不可直接作为动画路径: '+id)}}}
 if(d.faq!==undefined){array(d.faq,'faq');for(const f of d.faq){str(f.question,'faq.question');explanation(f.answer,'faq.answer');if(f.source!==undefined)str(f.source,'faq.source');if(f.nodeIds!==undefined){array(f.nodeIds,'faq.nodeIds');f.nodeIds.forEach(id=>ok(nodeIds.has(id),'FAQ 节点引用不存在: '+id))}}}
 const boxes=new Map([...d.groups,...d.nodes].map(n=>[n.id,n]));
 const routeIssues=[...d.edges,...(d.connectors||[])].flatMap(e=>auditRoute(e,boxes.get(e.from),boxes.get(e.to)));
 ok(!routeIssues.length,'连线可读性检查失败: '+JSON.stringify(routeIssues));
 return d;
}
function extract(html){const m=html.match(DATA_TAG);assert.ok(m,'缺少 canvas-data');return JSON.parse(m[1])}
function build(data){validate(data);const template=fs.readFileSync(templatePath,'utf8');assert.ok(DATA_TAG.test(template),'模板缺少 canvas-data');const json=JSON.stringify(data,null,2).replace(/</g,'\\u003c').replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');return template.replace(DATA_TAG,()=>'<script type="application/json" id="canvas-data">\n'+json+'\n</script>')}
module.exports={validate,extract,build};
if(require.main===module){try{const [input,output,...flags]=process.argv.slice(2);assert.ok(input&&output&&flags.every(f=>f==='--overwrite'),'用法: node build_canvas.cjs material.json output.html [--overwrite]');assert.notEqual(path.resolve(input),path.resolve(output),'输入和输出不能为同一文件');const data=JSON.parse(fs.readFileSync(input,'utf8')),html=build(data);fs.writeFileSync(output,html,{encoding:'utf8',flag:flags.includes('--overwrite')?'w':'wx'});console.log(JSON.stringify({output:path.resolve(output),nodes:data.nodes.length,bytes:Buffer.byteLength(html)},null,2))}catch(e){console.error(e.message);process.exitCode=1}}
