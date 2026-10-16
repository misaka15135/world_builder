import {$,element,notify} from '../core/ui.js';
function valueAt(parameters,path){const [stage,kind,id,key]=path.split('.');return kind==='districts'?parameters[stage].districts.find(d=>d.id===id)[key]:kind==='castle'?parameters[stage].castle[id]:parameters[stage][kind];}
export function adjustments(profile,start){
  let offered=null,base=null,busy=false;const inputs=new Map();
  $('#load-adjust').onclick=()=>{
    base=offered;const groups=new Map();$('#adjust-fields').replaceChildren();inputs.clear();
    for(const field of profile.fields){
      if(!groups.has(field.group)){const details=element('details','adjust-group');details.open=field.group==='地形与树林';details.append(element('summary','',field.group));const grid=element('div','field-pair');details.append(grid);$('#adjust-fields').append(details);groups.set(field.group,grid);}
      const label=element('label','',`${field.label} (${field.min}—${field.max})`),input=element('input');input.type='number';input.min=field.min;input.max=field.max;input.step=1;input.required=true;input.value=valueAt(base.parameters,field.path);input.dataset.parameter=field.path;label.append(input);groups.get(field.group).append(label);inputs.set(field.path,input);
    }
    $('#nature-adjust-form').hidden=false;$('#adjust-note').textContent=`基于 ${base.id.slice(0,8)} 重建新运行。只改变提交的参数；不调用API，不覆盖旧版本。范围内的组合仍可能不可行。`;
  };
  $('#nature-adjust-form').onsubmit=async event=>{
    event.preventDefault();if(busy||!base)return;
    const changes=Object.fromEntries([...inputs].map(([path,input])=>[path,Number(input.value)]).filter(([path,value])=>value!==valueAt(base.parameters,path)));
    if(!Object.keys(changes).length){notify('请先修改至少一个参数。',true);return;}
    try{busy=true;$('#apply-adjust').disabled=true;await start({pipeline:'nature047',mode:'adjust',source_id:base.id,changes});}
    catch(error){notify(error.message,true);}finally{busy=false;$('#apply-adjust').disabled=false;}
  };
  return {render(job,isBusy){
    const candidate=job?.pipeline==='nature047'&&job.status==='succeeded'&&job.parameters?job:null;
    if(candidate?.id!==offered?.id){base=null;$('#nature-adjust-form').hidden=true;}
    offered=candidate;busy=isBusy;$('#nature-adjust-panel').hidden=!offered;$('#load-adjust').disabled=busy;$('#apply-adjust').disabled=busy;
    inputs.forEach(input=>input.disabled=busy);
  }};
}
