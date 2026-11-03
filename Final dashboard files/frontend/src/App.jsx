import {useEffect,useState,useRef,useCallback} from 'react';
import {Sun,Zap,Gauge,Waves,BatteryCharging,Activity,ShieldCheck,CloudSun,RefreshCw,Bell,Download,CircleHelp,Thermometer,Cpu,LayoutDashboard,Settings2,AlertTriangle,Save,Wifi,Database,SlidersHorizontal,Upload,FileText,CheckCircle,XCircle,Info} from 'lucide-react';
import {AreaChart,Area,CartesianGrid,XAxis,YAxis,Tooltip,ResponsiveContainer,BarChart,Bar,LineChart,Line} from 'recharts';
import SolarScene from './SolarScene.jsx';

const API=localStorage.getItem('solary-api')||`${window.location.protocol}//${window.location.hostname}:8000`;
const pages={overview:'Overview',live:'Live monitoring',faults:'Fault detection',forecast:'Energy forecast',history:'Sensor history',device:'Device settings',config:'Configuration'};
const nav=[['overview',LayoutDashboard],['live',Activity],['faults',ShieldCheck],['forecast',Zap],['history',Waves],['device',Cpu],['config',Settings2]];
const n=(v,d=1)=>v==null?'—':Number(v).toFixed(d);

/* ─── Utility: source badge color ─── */
function sourceLabel(src) {
  if (!src) return 'DEMO';
  if (src === 'ESP32') return 'LIVE';
  if (src.includes('STALE')) return 'STALE';
  if (src === 'BASELINE') return 'BASELINE';
  return src;
}
function sourceClass(src) {
  if (src === 'ESP32') return 'live';
  if (src && src.includes('STALE')) return 'stale';
  return 'demo';
}

/* ─── Reusable Components ─── */

function Card({icon:Icon,label,value,unit,color,source='DEMO'}){
  const sl = sourceLabel(source);
  const sc = sourceClass(source);
  return <div className="metric">
    <div className="metrichead"><span className={'micon '+color}><Icon size={18}/></span><span>{label}</span></div>
    <div className="metricvalue">{value}<small>{unit}</small></div>
    <div className="sub">↗ <span className={`source-badge ${sc}`}>{sl}</span> reading</div>
  </div>
}

function State({loading,error,children}){
  if(loading)return <div className="state">Loading dashboard data...</div>;
  if(error)return <div className="state error"><AlertTriangle size={18}/><span>API unavailable. Start the backend to load live data.</span></div>;
  return children
}

function Chart({data,type='area'}){return <div className="chart"><ResponsiveContainer width="100%" height="100%">{type==='line'?<LineChart data={data}><CartesianGrid stroke="#253139" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="time" tick={{fill:'#7e8d92',fontSize:10}} axisLine={false} tickLine={false}/><YAxis tick={{fill:'#7e8d92',fontSize:10}} axisLine={false} tickLine={false}/><Tooltip contentStyle={{background:'#141e24',border:'1px solid #344148',borderRadius:8}}/><Line dataKey="power_w" name="Power (W)" stroke="#c4f46b" strokeWidth={2.5} dot={false}/></LineChart>:<AreaChart data={data}><defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c4f46b" stopOpacity=".25"/><stop offset="100%" stopColor="#c4f46b" stopOpacity="0"/></linearGradient></defs><CartesianGrid stroke="#253139" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="time" tick={{fill:'#7e8d92',fontSize:10}} axisLine={false} tickLine={false} interval={3}/><YAxis tick={{fill:'#7e8d92',fontSize:10}} axisLine={false} tickLine={false}/><Tooltip contentStyle={{background:'#141e24',border:'1px solid #344148',borderRadius:8}}/><Area dataKey="power_w" name="Power (W)" stroke="#c4f46b" strokeWidth={2.5} fill="url(#fill)"/></AreaChart>}</ResponsiveContainer></div>}

function Panel({label,title,description,children,action}){return <article className="panel"><div className="panelhead"><div><label>{label}</label><h3>{title}</h3>{description&&<p>{description}</p>}</div>{action}</div>{children}</article>}

function Status({label,value,ok=false}){return <div className="statusline"><span><i className={ok?'ok':''}/>{label}</span><b>{value}</b></div>}

function PageIntro({eyebrow,title,text,action}){return <section className="intro pageintro"><div><div className="eyebrow">{eyebrow}</div><h1>{title}<span>.</span></h1><p>{text}</p></div>{action}</section>}

/* ─── Anomaly Status Badge ─── */
function AnomalyBadge({status}) {
  if (!status) return null;
  const s = status.toLowerCase();
  let cls = 'anomaly-badge normal';
  if (s.includes('critical')) cls = 'anomaly-badge critical';
  else if (s.includes('warning')) cls = 'anomaly-badge warning';
  else if (s.includes('unavailable')) cls = 'anomaly-badge unavailable';
  return <span className={cls}>{status}</span>;
}

/* ─── Overview Page ─── */
function Overview({data,hist,fault,fc,anomaly,loading,error,refresh,horizon,onHorizonChange}){
  const src = data?.source || 'DEMO';
  const isLive = src === 'ESP32';
  const isStale = src?.includes('STALE');
  
  return <>
    <section className="intro">
      <div>
        <div className="eyebrow">— SOLAR ASSET OVERVIEW</div>
        <h1>Good morning<span>.</span></h1>
        <p>Here's what's happening with your solar system today.</p>
      </div>
      <div className="actions">
        <span className={`demo ${isLive ? 'live-mode' : isStale ? 'stale-mode' : ''}`}>
          ● {isLive ? 'LIVE DATA' : isStale ? 'STALE DATA' : 'DEMO DATA'}
        </span>
        <button className="outline" onClick={refresh}><RefreshCw size={14}/> Refresh</button>
        <button className="primary" onClick={()=>window.print()}><Download size={14}/> Export report</button>
      </div>
    </section>
    
    {!isLive && <div className="notice">
      <CircleHelp size={18}/>
      <div>
        <b>{isStale ? 'Stale data' : 'Prototype mode'}</b>
        <p>{isStale 
          ? `Last reading is ${Math.round(data?.data_age_seconds || 0)}s old. ESP32 may be disconnected.`
          : 'Sensor readings are simulated until a fresh ESP32 upload reaches the backend.'
        }</p>
      </div>
      <span>{isStale ? 'STALE' : 'NOT LIVE'}</span>
    </div>}
    
    <div className="sectiontitle">
      <div>
        <h2>Performance snapshot</h2>
        <p>Real-time overview of your solar asset</p>
      </div>
      {anomaly && <AnomalyBadge status={anomaly.status}/>}
    </div>
    
    <State loading={loading} error={error}>
      <section className="metrics">
        <Card icon={Zap} label="Current power" value={n(data?.panel_power_w,2)} unit=" W" color="lime" source={src}/>
        <Card icon={Gauge} label="Panel voltage" value={n(data?.panel_voltage_v,2)} unit=" V" color="blue" source={src}/>
        <Card icon={Waves} label="Panel current" value={n(data?.panel_current_a,3)} unit=" A" color="purple" source={src}/>
        <Card icon={BatteryCharging} label="Energy today" value={n(data?.energy_today_kwh,2)} unit=" kWh" color="orange" source={src}/>
      </section>
      <section className="scene-row"><SolarScene reading={data}/></section>
      <section className="twocol">
        <Panel label="ENERGY ANALYTICS" title="Power generation" description="Solar output throughout the day">
          <div className="legend"><span><i/> Power output <b>{n(data?.panel_power_w,2)} W</b></span><small className={`source-badge ${sourceClass(src)}`}>● {sourceLabel(src)} SERIES</small></div>
          <Chart data={hist}/>
          <div className="foot"><span>● Daylight profile</span><span>Refreshes every 5 seconds</span></div>
        </Panel>
        <Environment data={data} source={src}/>
      </section>
      <section className="twocol lower">
        <AnomalySummary anomaly={anomaly}/>
        <ForecastSummary data={fc}/>
      </section>
      <section className="twocol lower">
        <FaultSummary data={fault}/>
      </section>
    </State>
  </>
}

/* ─── Environment Panel ─── */
function Environment({data,source='DEMO'}){
  const sl = sourceLabel(source);
  const sc = sourceClass(source);
  return <Panel label="ENVIRONMENT" title="Panel conditions" description="Local sensor readings" action={<Sun className="softicon"/>}>
    <div className="weather">
      <div className="sunorb"><Sun size={34}/></div>
      <div><small>Ambient temperature</small><div className="temp">{n(data?.temperature_c)}<small>°C</small></div><em>{data?.temperature_c != null ? (data.temperature_c > 35 ? 'Elevated' : data.temperature_c < 10 ? 'Cool' : 'Comfortable operating range') : 'No reading'}</em></div>
    </div>
    <div className="envstats">
      <div><span><Waves/>Humidity</span><b>{n(data?.humidity_pct)}<small>%</small></b></div>
      <div><span><Sun/>Light intensity</span><b>{n(data?.light_pct,0)}<small>%</small></b></div>
    </div>
    <div className="foot">● Sensor stream <span className={`source-badge ${sc}`}>{sl}</span></div>
  </Panel>
}

/* ─── Anomaly Summary Panel ─── */
function AnomalySummary({anomaly}) {
  const status = anomaly?.status || 'Sensor Unavailable';
  const alerts = anomaly?.alerts || [];
  const hasElectrical = anomaly?.has_electrical || false;
  
  return <Panel label="ANOMALY DETECTION" title="Electrical anomalies" description="Threshold-based anomaly monitoring"
    action={<AnomalyBadge status={status}/>}>
    <div className="anomaly-info">
      <div className="anomaly-status-row">
        <span className={`anomaly-indicator ${status.toLowerCase().includes('critical') ? 'critical' : status.toLowerCase().includes('warning') ? 'warning' : status.toLowerCase().includes('unavailable') ? 'unavailable' : 'normal'}`}/>
        <div>
          <b>System Status: {status}</b>
          <p>{!hasElectrical 
            ? 'Electrical sensors (INA219) not connected. Monitoring environmental parameters only.'
            : alerts.length === 0 ? 'All parameters within normal operating range.' : `${alerts.filter(a=>a.level!=='info').length} alert(s) detected.`
          }</p>
        </div>
      </div>
    </div>
    {alerts.filter(a => a.level !== 'info').length > 0 && (
      <div className="alert-list">
        {alerts.filter(a => a.level !== 'info').map((alert, i) => (
          <div key={i} className={`alert-item ${alert.level}`}>
            {alert.level === 'critical' ? <XCircle size={14}/> : <AlertTriangle size={14}/>}
            <span>{alert.reason}</span>
          </div>
        ))}
      </div>
    )}
    {alerts.filter(a => a.level !== 'info').length === 0 && (
      <div className="faults">
        <div><small>01</small><span>Temperature</span><em>{anomaly?.has_environmental ? 'Normal' : 'No data'}</em></div>
        <div><small>02</small><span>Humidity</span><em>{anomaly?.has_environmental ? 'Normal' : 'No data'}</em></div>
        <div><small>03</small><span>Voltage</span><em>{hasElectrical ? 'Normal' : 'Sensor unavailable'}</em></div>
        <div><small>04</small><span>Current</span><em>{hasElectrical ? 'Normal' : 'Sensor unavailable'}</em></div>
        <div><small>05</small><span>Power</span><em>{hasElectrical ? 'Normal' : 'Sensor unavailable'}</em></div>
      </div>
    )}
    <div className="foot">
      <span>Last check: {anomaly?.last_check ? new Date(anomaly.last_check).toLocaleTimeString() : 'Never'}</span>
      <span>Thresholds: documented & configurable</span>
    </div>
  </Panel>
}

/* ─── Fault Detection Panel ─── */
function FaultSummary({data,full=false}){
  const modelLoaded = data?.model_loaded || false;
  const classes = data?.classes || [{name:'MultiHotSpot'},{name:'SingleHotSpot'},{name:'StringOpenCircuit'}];
  
  return <Panel label="AI DIAGNOSTICS" title="Fault detection" description="MobileNetV2 solar panel health assessment" 
    action={<span className="modeltag">{modelLoaded ? '● MODEL READY' : '● MODEL NOT CONNECTED'}</span>}>
    <div className="await">
      <span><ShieldCheck size={28}/></span>
      <div>
        <b>{modelLoaded ? 'Model loaded — ready for inference' : 'Awaiting model integration'}</b>
        <p>{data?.message || 'Three fault classes will appear here after your trained models are connected.'}</p>
      </div>
    </div>
    <div className="faults">
      {classes.map((f,i)=><div key={f.name||i}>
        <small>0{i+1}</small>
        <span>{f.name}</span>
        <em>{f.status||'Not evaluated'}{f.confidence_pct > 0 ? ` (${f.confidence_pct}%)` : ''}</em>
      </div>)}
    </div>
    {data?.input_requirements && <div className="warning"><Info size={14}/> {data.input_requirements.note}</div>}
    {!modelLoaded && data?.model_error && <div className="warning"><AlertTriangle size={14}/> {data.model_error}</div>}
    {full&&<div className="empty-note">Latest event: {data?.latest_event||'No model inference has been run.'}</div>}
  </Panel>
}

/* ─── Forecast Summary Panel ─── */
function ForecastSummary({data,full=false}){
  const [horizon,setHorizon]=useState(12);
  const [forecast,setForecast]=useState(data);
  const [forecastLoading,setForecastLoading]=useState(false);
  
  useEffect(()=>setForecast(data),[data]);
  
  async function changeHorizon(value){
    setHorizon(value);
    setForecastLoading(true);
    try{
      const response=await fetch(`${API}/api/forecast?horizon=${value}`);
      if(!response.ok)throw Error('Forecast API error');
      setForecast(await response.json());
    }catch{}finally{setForecastLoading(false)}
  }
  
  const points=(forecast?.points||[]).slice(0,horizon+1);
  const total=points.slice(1).reduce((sum,point)=>sum+Number(point.energy_kwh||0),0);
  const src = forecast?.source || 'DEMO';
  
  return <Panel label="PREDICTIVE ANALYTICS" title="Energy forecast" description={`${sourceLabel(src)} — next ${horizon} hours`} 
    action={<div className="forecast-actions">
      <div className="switch" role="group" aria-label="Forecast horizon">
        {[12,24].map(value=><button key={value} className={horizon===value?'sel':''} onClick={()=>changeHorizon(value)}>{value}H</button>)}
      </div>
      <span className={`forecasttag ${src === 'BASELINE' ? 'baseline-tag' : ''}`}>{sourceLabel(src)}</span>
    </div>}>
    <div className="forecastvalue">
      <div><small>Predicted energy, {horizon}h horizon</small><b>{forecastLoading?'...':n(total,3)} <small>kWh</small></b></div>
      <CloudSun size={25}/>
    </div>
    <div className="forecastchart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points}>
          <CartesianGrid stroke="#253139" strokeDasharray="3 5" vertical={false}/>
          <XAxis dataKey="time" tick={{fill:'#7e8d92',fontSize:9}} axisLine={false} tickLine={false}/>
          <YAxis dataKey="predicted_power_w" unit=" W" tick={{fill:'#7e8d92',fontSize:10}} axisLine={false} tickLine={false}/>
          <Tooltip contentStyle={{background:'#141e24',border:'1px solid #344148',borderRadius:8}}/>
          <Line dataKey="predicted_power_w" name="Predicted power (W)" stroke="#c4f46b" strokeWidth={2.5} dot={false}/>
        </LineChart>
      </ResponsiveContainer>
    </div>
    <div className="forecast-meta">
      <span>Predicted power (W)</span>
      <span>Energy integrated from hourly samples</span>
    </div>
    {forecast?.methodology && <div className="forecast-methodology"><small><b>Method:</b> {forecast.methodology}</small></div>}
    <div className="warning violet"><CircleHelp size={14}/> {forecast?.message||'Not generated by a trained forecasting model.'}</div>
    {full&&<>
      <div className="summaryrow"><span>Horizon</span><b>{horizon} hours</b></div>
      <div className="summaryrow"><span>Units</span><b>Power: W, Energy: kWh</b></div>
      {forecast?.limitations && <div className="summaryrow limitations">
        <span>Limitations</span>
        <ul>{forecast.limitations.map((l,i)=><li key={i}>{l}</li>)}</ul>
      </div>}
    </>}
  </Panel>
}

/* ─── Live Monitoring Page ─── */
function Live({data,hist,anomaly,sensorHealth,loading,error}){
  const src = data?.source || 'DEMO';
  const sensors = sensorHealth?.sensors || {};
  return <>
    <PageIntro eyebrow="— LIVE SENSOR STREAM" title="Live monitoring" text="Current telemetry from the connected sensor pipeline."/>
    <State loading={loading} error={error}>
      <div className="metrics">
        <Card icon={Gauge} label="Panel voltage" value={n(data?.panel_voltage_v,2)} unit=" V" color="blue" source={src}/>
        <Card icon={Waves} label="Panel current" value={n(data?.panel_current_a,3)} unit=" A" color="purple" source={src}/>
        <Card icon={Zap} label="Calculated power" value={n(data?.panel_power_w,2)} unit=" W" color="lime" source={src}/>
        <Card icon={Thermometer} label="Temperature" value={n(data?.temperature_c)} unit=" °C" color="orange" source={src}/>
      </div>
      <section className="twocol">
        <Panel label="LIVE TELEMETRY" title="Recent power readings" description="Updated automatically every 5 seconds">
          <Chart data={hist} type="line"/>
          <div className="foot">
            <span>● {sourceLabel(src)} sensor stream</span>
            <span>{data?.timestamp?new Date(data.timestamp).toLocaleTimeString():'Awaiting update'}{data?.data_age_seconds != null ? ` (${Math.round(data.data_age_seconds)}s ago)` : ''}</span>
          </div>
        </Panel>
        <Panel label="SENSOR STATUS" title="Environmental readings" description="Values supplied by /api/readings">
          <div className="statuslist">
            <Status label="Data source" value={src === 'ESP32' ? 'ESP32 (Live)' : src?.includes('STALE') ? 'ESP32 (Stale)' : 'Demo simulation'} ok={src === 'ESP32'}/>
            <Status label="DHT11" value={sensors.dht11?.status || 'Awaiting data'} ok={sensors.dht11?.status === 'Reporting'}/>
            <Status label="LDR" value={sensors.ldr?.status || 'Awaiting data'} ok={sensors.ldr?.status === 'Reporting'}/>
            <Status label="Humidity" value={`${n(data?.humidity_pct)} %`}/>
            <Status label="Light intensity" value={`${n(data?.light_pct,0)} %`}/>
            <Status label="LDR raw" value={data?.ldr_raw != null ? String(data.ldr_raw) : '—'}/>
            <Status label="INA219" value={sensors.ina219?.status || 'Awaiting validation'}/>
            <Status label="System status" value={data?.system_status||'Awaiting data'}/>
            {data?.is_stale && <Status label="Data age" value={`${Math.round(data.data_age_seconds || 0)} seconds`}/>}
          </div>
          {anomaly && <div style={{marginTop:12}}><AnomalyBadge status={anomaly.status}/></div>}
        </Panel>
      </section>
    </State>
  </>
}

/* ─── Fault Detection Page (with upload) ─── */
function FaultPage({fault}){
  const [imageFile, setImageFile] = useState(null);
  const [annotationFile, setAnnotationFile] = useState(null);
  const [predicting, setPredicting] = useState(false);
  const [results, setResults] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const imageRef = useRef(null);
  const annotRef = useRef(null);

  async function handlePredict(e) {
    e.preventDefault();
    if (!imageFile || !annotationFile) {
      setUploadError('Both an image file and a YOLO annotation (.txt) file are required.');
      return;
    }
    setPredicting(true);
    setUploadError(null);
    setResults(null);

    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('annotations', annotationFile);

    try {
      const response = await fetch(`${API}/api/faults/predict`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        setUploadError(data.detail || 'Prediction failed');
      } else {
        setResults(data);
      }
    } catch (err) {
      setUploadError(`Network error: ${err.message}`);
    } finally {
      setPredicting(false);
    }
  }

  return <>
    <PageIntro eyebrow="— AI DIAGNOSTICS" title="Fault detection" text="MobileNetV2 three-class classifier for solar panel fault assessment."/>
    <FaultSummary data={fault} full/>
    
    <Panel label="IMAGE UPLOAD" title="Run fault inference" description="Upload a solar panel image with YOLO annotations to classify faults">
      <form className="upload-form" onSubmit={handlePredict}>
        <div className="upload-row">
          <div className="upload-box" onClick={() => imageRef.current?.click()}>
            <Upload size={24}/>
            <b>{imageFile ? imageFile.name : 'Select panel image'}</b>
            <small>JPG, PNG, BMP, TIFF</small>
            <input ref={imageRef} type="file" accept=".jpg,.jpeg,.png,.bmp,.tiff" hidden onChange={e => setImageFile(e.target.files[0])}/>
          </div>
          <div className="upload-box" onClick={() => annotRef.current?.click()}>
            <FileText size={24}/>
            <b>{annotationFile ? annotationFile.name : 'Select YOLO annotations'}</b>
            <small>.txt file (class x y w h)</small>
            <input ref={annotRef} type="file" accept=".txt" hidden onChange={e => setAnnotationFile(e.target.files[0])}/>
          </div>
        </div>
        
        <button className="primary" type="submit" disabled={predicting || !imageFile || !annotationFile}>
          {predicting ? 'Running inference...' : <><ShieldCheck size={14}/> Classify faults</>}
        </button>
        
        {uploadError && <div className="upload-error"><AlertTriangle size={14}/> {uploadError}</div>}
      </form>
      
      {results && <div className="prediction-results">
        <h4>Classification Results</h4>
        <div className="result-meta">
          <span>Image: {results.image_filename}</span>
          <span>Regions analyzed: {results.regions_analyzed}</span>
          <span>{new Date(results.timestamp).toLocaleString()}</span>
        </div>
        {results.results.map((r, i) => (
          <div key={i} className="result-card">
            <div className="result-header">
              <b>Region #{r.region_index + 1}</b>
              <span className="result-class">{r.predicted_class}</span>
              <span className="result-confidence">{r.confidence_pct}%</span>
            </div>
            <div className="result-probs">
              {Object.entries(r.probabilities).map(([name, pct]) => (
                <div key={name} className="prob-bar">
                  <span>{name}</span>
                  <div className="prob-track"><div className="prob-fill" style={{width: `${pct}%`}}/></div>
                  <span>{pct}%</span>
                </div>
              ))}
            </div>
          </div>
        ))}
        {results.note && <div className="warning"><Info size={14}/> {results.note}</div>}
      </div>}
    </Panel>
  </>
}

/* ─── History Page ─── */
function History({hist,histSource,loading,error}){
  const [filter,setFilter]=useState('all');
  const [range,setRange]=useState('24');
  const rows=hist.filter(p=>filter==='all'||filter==='power'&&p.power_w!=null).slice(-Number(range));
  
  function download(){
    const body=['Timestamp,Power (W),Voltage (V),Current (A),Temperature (C),Humidity (%),Light (%)',...rows.map(p=>`${p.timestamp||p.time},${p.power_w??''},${p.voltage_v??''},${p.current_a??''},${p.temperature_c??''},${p.humidity_pct??''},${p.light_pct??''}`)].join('\n');
    const a=document.createElement('a');
    a.href=URL.createObjectURL(new Blob([body],{type:'text/csv'}));
    a.download='solar-history.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  }
  
  return <>
    <PageIntro eyebrow="— SENSOR HISTORY" title="Sensor history" text="Historical values from the sensor data pipeline." action={<button className="outline" onClick={download}><Download size={14}/> Export CSV</button>}/>
    <Panel label="HISTORY TABLE" title="Sensor readings history" description={`Source: ${histSource || 'DEMO'}`}>
      <div className="filters">
        <select value={filter} onChange={e=>setFilter(e.target.value)}>
          <option value="all">All metrics</option>
          <option value="power">Power and voltage</option>
        </select>
        <select value={range} onChange={e=>setRange(e.target.value)}>
          <option value="12">Last 12 points</option>
          <option value="24">Last 24 points</option>
          <option value="50">Last 50 points</option>
          <option value="100">Last 100 points</option>
        </select>
      </div>
      <State loading={loading} error={error}>
        {rows.length?<div className="tablewrap"><table><thead><tr>
          <th>Timestamp</th><th>Voltage (V)</th><th>Power (W)</th><th>Current (A)</th><th>Temperature (°C)</th><th>Humidity (%)</th><th>Light (%)</th>
        </tr></thead><tbody>{rows.map((p,i)=><tr key={(p.timestamp||p.time)+i}>
          <td>{p.timestamp?new Date(p.timestamp).toLocaleString():p.time}</td><td>{p.voltage_v??'—'}</td><td>{p.power_w??'—'}</td><td>{p.current_a??'—'}</td><td>{p.temperature_c??'—'}</td><td>{p.humidity_pct??'—'}</td><td>{p.light_pct??'—'}</td>
        </tr>)}</tbody></table></div>:<div className="empty-note">No historical readings are available for the selected filters.</div>}
      </State>
    </Panel>
  </>
}

/* ─── Device Settings Page ─── */
function Device({online,updated,sensorHealth}){
  const sensors = sensorHealth?.sensors || {};
  return <>
    <PageIntro eyebrow="— SYSTEM HEALTH" title="Device settings" text="Connection and integration status for the solar asset."/>
    <section className="twocol">
      <Panel label="CONNECTIONS" title="Device status" description="Hardware connectivity status">
        <div className="statuslist">
          <Status label="Backend API" value={online?'Connected':'Not connected'} ok={online}/>
          <Status label="ESP32" value={sensors.esp32?.status || 'Not connected'} ok={sensors.esp32?.status === 'Connected'}/>
          <Status label="INA219" value={sensors.ina219?.status || 'Awaiting integration'} ok={sensors.ina219?.status === 'Reporting'}/>
          <Status label="DHT11" value={sensors.dht11?.status || 'Awaiting integration'} ok={sensors.dht11?.status === 'Reporting'}/>
          <Status label="LDR" value={sensors.ldr?.status || 'Awaiting integration'} ok={sensors.ldr?.status === 'Reporting'}/>
          <Status label="Fault Model" value={sensors.fault_model?.status || 'Not loaded'} ok={sensors.fault_model?.status === 'Loaded'}/>
        </div>
      </Panel>
      <Panel label="LATEST READINGS" title="Sensor values" description="Most recent values from each sensor">
        <div className="statuslist">
          <Status label="Temperature" value={sensors.dht11?.last_temperature_c != null ? `${sensors.dht11.last_temperature_c}°C` : 'No data'}/>
          <Status label="Humidity" value={sensors.dht11?.last_humidity_pct != null ? `${sensors.dht11.last_humidity_pct}%` : 'No data'}/>
          <Status label="LDR raw" value={sensors.ldr?.last_raw_value != null ? String(sensors.ldr.last_raw_value) : 'No data'}/>
          <Status label="Light %" value={sensors.ldr?.last_light_pct != null ? `${sensors.ldr.last_light_pct}%` : 'No data'}/>
          <Status label="Voltage" value={sensors.ina219?.last_voltage_v != null ? `${sensors.ina219.last_voltage_v}V` : 'Not connected'}/>
          <Status label="Current" value={sensors.ina219?.last_current_a != null ? `${sensors.ina219.last_current_a}A` : 'Not connected'}/>
          <Status label="Power" value={sensors.ina219?.last_power_w != null ? `${sensors.ina219.last_power_w}W` : 'Not connected'}/>
        </div>
        {sensors.esp32?.data_age_seconds != null && (
          <div className="foot"><span>Data age: {Math.round(sensors.esp32.data_age_seconds)}s</span></div>
        )}
      </Panel>
    </section>
    <Panel label="UPDATE POLICY" title="Refresh status" description="Dashboard polling configuration">
      <div className="statuslist">
        <Status label="Last successful update" value={online?updated.toLocaleTimeString():'No successful update'}/>
        <Status label="Configured refresh interval" value="5 seconds"/>
        <Status label="Overall system" value={sensorHealth?.overall || 'Offline'}/>
        <Status label="Data source" value={sensorHealth?.data_source || 'None'}/>
      </div>
    </Panel>
  </>
}

/* ─── Configuration Page ─── */
function Config({refreshMs,setRefreshMs}){
  const [value,setValue]=useState(String(refreshMs/1000));
  const [api,setApi]=useState(API);
  const [saved,setSaved]=useState(false);
  function save(e){
    e.preventDefault();
    const seconds=Number(value);
    if(!Number.isFinite(seconds)||seconds<2||seconds>300)return;
    localStorage.setItem('solary-api',api.trim());
    localStorage.setItem('solary-refresh-ms',String(seconds*1000));
    setRefreshMs(seconds*1000);
    setSaved(true);
  }
  return <>
    <PageIntro eyebrow="— WORKSPACE CONFIGURATION" title="Configuration" text="Safe UI preferences for this local dashboard."/>
    <Panel label="PREFERENCES" title="Dashboard configuration" description="Changes are stored locally in this browser.">
      <form className="configform" onSubmit={save}>
        <label>Dashboard refresh interval (seconds)<input type="number" min="2" max="300" value={value} onChange={e=>{setValue(e.target.value);setSaved(false)}}/></label>
        <label>API base URL<input value={api} onChange={e=>{setApi(e.target.value);setSaved(false)}}/></label>
        <div className="configgrid">
          <Status label="Data mode" value={saved ? 'Saved' : 'Pending'}/>
          <Status label="Sensor availability" value="Per /api/sensor-health"/>
          <Status label="Model integration" value="Per /api/faults"/>
        </div>
        <button className="primary" type="submit"><Save size={14}/> Save preferences</button>
        {saved&&<span className="saved">Preferences saved locally.</span>}
      </form>
    </Panel>
  </>
}

/* ─── Main App ─── */
export default function App(){
  const [page,setPage]=useState(window.location.hash.slice(1)||'overview');
  const [data,setData]=useState(null);
  const [hist,setHist]=useState([]);
  const [histSource,setHistSource]=useState('DEMO');
  const [fault,setFault]=useState(null);
  const [fc,setFc]=useState(null);
  const [anomaly,setAnomaly]=useState(null);
  const [sensorHealth,setSensorHealth]=useState(null);
  const [online,setOnline]=useState(false);
  const [updated,setUpdated]=useState(new Date());
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState(false);
  const hasLoaded=useRef(false);
  const requestInFlight=useRef(false);
  const [refreshMs,setRefreshMs]=useState(Number(localStorage.getItem('solary-refresh-ms'))||5000);

  function navigate(next){setPage(next);window.location.hash=next}

  const load = useCallback(async function(){
    if(requestInFlight.current)return;
    requestInFlight.current=true;
    if(!hasLoaded.current)setLoading(true);
    try{
      const responses=await Promise.all([
        'readings','history','faults','forecast','anomalies','sensor-health'
      ].map(p=>fetch(`${API}/api/${p}`).then(r=>{if(!r.ok)throw Error('API error');return r.json()})));
      setData(responses[0]);
      setHist(responses[1].points||[]);
      setHistSource(responses[1].source||'DEMO');
      setFault(responses[2]);
      setFc(responses[3]);
      setAnomaly(responses[4]);
      setSensorHealth(responses[5]);
      setOnline(true);
      setUpdated(new Date());
      setError(false);
    }catch{
      setOnline(false);
      setError(true);
    }finally{
      hasLoaded.current=true;
      requestInFlight.current=false;
      setLoading(false);
    }
  }, []);

  useEffect(()=>{
    const onHash=()=>setPage(window.location.hash.slice(1)||'overview');
    window.addEventListener('hashchange',onHash);
    load();
    const timer=setInterval(load,refreshMs);
    return()=>{clearInterval(timer);window.removeEventListener('hashchange',onHash)};
  },[refreshMs,load]);

  const src = data?.source || 'DEMO';
  const isLive = src === 'ESP32';
  const isStale = src?.includes('STALE');

  const content=
    page==='live'?<Live data={data} hist={hist} anomaly={anomaly} sensorHealth={sensorHealth} loading={loading} error={error}/>
    :page==='faults'?<FaultPage fault={fault}/>
    :page==='forecast'?<><PageIntro eyebrow="— PREDICTIVE ANALYTICS" title="Energy forecast" text="Baseline forecast using solar irradiance model."/><ForecastSummary data={fc} full/></>
    :page==='history'?<History hist={hist} histSource={histSource} loading={loading} error={error}/>
    :page==='device'?<Device online={online} updated={updated} sensorHealth={sensorHealth}/>
    :page==='config'?<Config refreshMs={refreshMs} setRefreshMs={setRefreshMs}/>
    :<Overview data={data} hist={hist} fault={fault} fc={fc} anomaly={anomaly} loading={loading} error={error} refresh={load}/>;

  return <div className="shell">
    <aside className="sidebar">
      <div className="logo"><span><Sun size={23}/></span><div><b>solary<span>.</span></b><small>ENERGY INTELLIGENCE</small></div></div>
      <label>WORKSPACE</label>
      {nav.slice(0,5).map(([id,Icon])=><button key={id} className={'nav '+(page===id?'active':'')} onClick={()=>navigate(id)}><Icon/><span>{pages[id]}</span></button>)}
      <label className="sys">SYSTEM</label>
      {nav.slice(5).map(([id,Icon])=><button key={id} className={'nav '+(page===id?'active':'')} onClick={()=>navigate(id)}><Icon/><span>{pages[id]}</span></button>)}
      <div className="spacer"/>
      <div className="plant">
        <div><Sun size={16}/> <span className="online">● {isLive ? 'LIVE' : online ? 'API ONLINE' : 'API OFFLINE'}</span></div>
        <b>Rooftop Solar</b>
        <small>Prototype · 19.4 V panel</small>
        <div className="progress"><i style={{width: isLive ? '100%' : online ? '86%' : '20%'}}/></div>
        <small>System status <strong>{isLive ? 'Live' : online ? 'Operational' : 'Waiting'}</strong></small>
      </div>
      <div className="user"><span>SI</span><div><b>Solar Intelligence</b><small>Local prototype</small></div></div>
    </aside>
    <main>
      <header>
        <div className="crumb">Workspace <span>/</span> <b>{pages[page]||pages.overview}</b></div>
        <div className="headright">
          <span className={`connect ${isLive ? 'connect-live' : ''}`}><i/> {isLive ? 'LIVE DATA' : online ? 'SYSTEM CONNECTED' : 'CONNECTING'} · {updated.toLocaleTimeString()}</span>
          <button className="square" onClick={load} aria-label="Refresh data"><RefreshCw size={16}/></button>
          <button className="square" aria-label="Notifications"><Bell size={16}/></button>
          <span className="userbadge">SI</span>
        </div>
      </header>
      {!isLive && <div className="notice globalnotice">
        <CircleHelp size={18}/>
        <div>
          <b>{isStale ? 'Stale data' : 'Prototype mode'}</b>
          <p>{isStale 
            ? 'ESP32 data is stale. Sensor may be disconnected or powered off.'
            : 'Demo readings are clearly labelled. No fresh ESP32 reading has reached the API.'}</p>
        </div>
        <span>{isStale ? 'STALE' : 'NOT LIVE'}</span>
      </div>}
      {isLive && <div className="notice live-notice globalnotice">
        <CheckCircle size={18}/>
        <div>
          <b>Live data active</b>
          <p>Receiving real sensor readings from ESP32. {anomaly?.status && `Anomaly status: ${anomaly.status}`}</p>
        </div>
        <span>LIVE</span>
      </div>}
      {content}
      <footer>© 2026 SOLARY INTELLIGENCE <span>AI-BASED SOLAR PANEL FAULT DETECTION</span><span>API {online?'CONNECTED':'DISCONNECTED'} · Last update {updated.toLocaleTimeString()}</span></footer>
    </main>
  </div>
}
