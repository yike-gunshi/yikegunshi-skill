// Pure geometry checks shared by static builds and custom/folding renderers.
// Call with the visible endpoint boxes after any collapse/expand projection.
function auditRoute(edge,from,to,options={}){
 const {maxBends=6,minLead=16,minSegment=12,tolerance=2}=options,issues=[];
 const add=(code,detail)=>issues.push({edge:edge.id||edge.from+'>'+edge.to,code,detail});
 const compact=points=>{const out=[];for(const p of points){if(out.length&&p[0]===out.at(-1)[0]&&p[1]===out.at(-1)[1])continue;while(out.length>1){const a=out.at(-2),b=out.at(-1);if((a[0]===b[0]&&b[0]===p[0]&&(b[1]-a[1])*(p[1]-b[1])>=0)||(a[1]===b[1]&&b[1]===p[1]&&(b[0]-a[0])*(p[0]-b[0])>=0))out.pop();else break}out.push(p)}return out};
 const p=compact(edge.points),drawn=compact(edge.renderPoints||edge.points),length=(a,b)=>Math.hypot(b[0]-a[0],b[1]-a[1]);
 const side=(box,point)=>{
  if(!box)return null;const [x,y]=point;
  if(x>=box.x-tolerance&&x<=box.x+box.w+tolerance){if(Math.abs(y-box.y)<=tolerance)return [0,-1];if(Math.abs(y-box.y-box.h)<=tolerance)return [0,1]}
  if(y>=box.y-tolerance&&y<=box.y+box.h+tolerance){if(Math.abs(x-box.x)<=tolerance)return [-1,0];if(Math.abs(x-box.x-box.w)<=tolerance)return [1,0]}
  return null;
 };
 if(p.length<2){add('empty','路径没有长度');return issues}
 for(const [box,index,next,label] of [[from,0,1,'起点'],[to,p.length-1,p.length-2,'终点']]){
  if(!box)continue;const n=side(box,p[index]);
  if(!n){add('endpoint',label+' 未落在可见目标边界');continue}
  const d=[p[next][0]-p[index][0],p[next][1]-p[index][1]];
  if(d[0]*n[1]!==d[1]*n[0]||d[0]*n[0]+d[1]*n[1]<=0)add('tangent',label+' 未沿边界法向连接');
 }
 if(drawn.length-2>maxBends)add('bends','折点过多: '+(drawn.length-2));
 for(let i=1;i<drawn.length;i++){
  const a=drawn[i-1],b=drawn[i];
  if(a[0]!==b[0]&&a[1]!==b[1])add('diagonal','正交路径含斜线');
  const terminal=i===1||i===drawn.length-1;
  // A straight short link has no corner consuming its terminal lead.
  const min=drawn.length===2?minSegment:terminal?minLead:minSegment;
  if(length(a,b)<min)add(terminal?'lead':'short-segment','第 '+i+' 段过短: '+length(a,b));
 }
 return issues;
}
module.exports={auditRoute};
