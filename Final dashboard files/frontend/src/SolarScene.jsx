import {Sun, MapPin} from 'lucide-react';

export default function SolarScene({reading}) {
  const power = reading?.panel_power_w == null ? '--' : `${Number(reading.panel_power_w).toFixed(2)} W`;
  const temperature = reading?.temperature_c == null ? '--' : `${Number(reading.temperature_c).toFixed(1)} C`;
  const cells = Array.from({length: 24}, (_, index) => index);

  return <article className="solar-scene panel" aria-label="Animated demo solar panel visualization">
    <div className="scene-head"><div><label>SOLAR POSITION</label><h3>Rooftop panel</h3><p>Illustrative scene · live readings below</p></div><span className="live-tag"><i/> DEMO LIVE</span></div>
    <div className="scene-canvas">
      <div className="scene-stars" aria-hidden="true"/>
      <div className="scene-sun"><Sun size={30}/></div>
      <svg className="trajectory" viewBox="0 0 640 260" role="img" aria-label="Illustrative sun trajectory">
        <path d="M 42 205 C 170 10, 455 10, 598 205"/>
        <circle className="trajectory-dot" cx="42" cy="205" r="4"/>
        <circle className="trajectory-dot" cx="598" cy="205" r="4"/>
      </svg>
      <span className="direction north">N</span><span className="direction east">E</span><span className="direction south">S</span><span className="direction west">W</span>
      <div className="platform"><div className="platform-glow"/><div className="panel-array">{cells.map(cell => <span key={cell}/>)}</div><div className="panel-leg left"/><div className="panel-leg right"/></div>
      <div className="scene-label sunrise"><small>Sunrise</small><b>06:03 AM</b></div><div className="scene-label sunset"><small>Sunset</small><b>06:09 PM</b></div>
      <div className="position-card"><span><MapPin size={12}/> Current position</span><b>Illustrative</b><small>Solar elevation 52 deg</small></div>
    </div>
    <div className="scene-stats"><div><small>Current power</small><b>{power}</b></div><div><small>Panel tilt</small><b>20 deg <em>DEMO</em></b></div><div><small>Azimuth</small><b>180 deg <em>DEMO</em></b></div><div><small>Temperature</small><b>{temperature}</b></div></div>
  </article>;
}
