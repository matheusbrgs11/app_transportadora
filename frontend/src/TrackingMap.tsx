import {useEffect,useRef,useState} from 'react';
import {importLibrary,setOptions} from '@googlemaps/js-api-loader';

export type MapDriver={id:string;nome:string;latitude:number;longitude:number};
const key=import.meta.env.VITE_GOOGLE_MAPS_JS_KEY;
const mapId=import.meta.env.VITE_GOOGLE_MAPS_MAP_ID;
let configured=false;

export default function TrackingMap({drivers}:{drivers:MapDriver[]}){
 const element=useRef<HTMLDivElement>(null),map=useRef<google.maps.Map|null>(null);
 const markers=useRef<google.maps.marker.AdvancedMarkerElement[]>([]);
 const [error,setError]=useState('');
 useEffect(()=>{
  if(!key||!mapId||!element.current)return;
  let cancelled=false;
  async function draw(){
   if(!configured){setOptions({key,v:'weekly',language:'pt-BR',region:'BR'});configured=true;}
   const [{Map},{AdvancedMarkerElement,PinElement}]=await Promise.all([
    importLibrary('maps') as Promise<google.maps.MapsLibrary>,
    importLibrary('marker') as Promise<google.maps.MarkerLibrary>]);
   if(cancelled||!element.current)return;
   if(!map.current)map.current=new Map(element.current,{center:{lat:-15.7801,lng:-47.9292},zoom:5,mapId,
    mapTypeControl:false,streetViewControl:false,fullscreenControl:true});
   markers.current.forEach(marker=>{marker.map=null;});markers.current=[];
   const bounds=new google.maps.LatLngBounds();
   for(const driver of drivers){
    const position={lat:driver.latitude,lng:driver.longitude};
    const pin=new PinElement({background:'#ed672c',borderColor:'#b84a18',glyphColor:'#ffffff'});
    markers.current.push(new AdvancedMarkerElement({map:map.current,position,title:driver.nome,content:pin.element}));
    bounds.extend(position);
   }
   if(drivers.length)map.current.fitBounds(bounds,60);
   setError('');
  }
  draw().catch(()=>{if(!cancelled)setError('Não foi possível carregar o mapa. Confira a chave e a conexão.');});
  return()=>{cancelled=true;markers.current.forEach(marker=>{marker.map=null;});markers.current=[];};
 },[drivers]);
 if(!key||!mapId)return <p className="tracking-map-note">Mapa simultâneo aguardando configuração do Google Maps. Os links individuais continuam disponíveis.</p>;
 return <div className="tracking-map-wrap"><div ref={element} className="tracking-map" role="img" aria-label="Últimas posições recentes dos motoristas no Google Maps"/>
  {error&&<p role="alert">{error}</p>}<p>{drivers.length} motorista(s) com posição recente no mapa. Posições antigas não aparecem como atuais.</p></div>;
}
