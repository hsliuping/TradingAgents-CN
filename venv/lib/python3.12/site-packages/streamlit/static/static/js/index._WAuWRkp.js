import{s as i,k as m,r as c,j as e}from"./index.CbQtRkVt.js";import{P as l,R as p}from"./RenderInPortalIfExists.D6a0mMll.js";const d=""+new URL("../media/flake-0.DgWaVvm5.png",import.meta.url).href,f=""+new URL("../media/flake-1.B2r5AHMK.png",import.meta.url).href,g=""+new URL("../media/flake-2.BnWSExPC.png",import.meta.url).href,o=150,r=150,E=10,S=90,u=4e3,n=(t,a=0)=>Math.random()*(t-a)+a,x=()=>m(`from{transform:translateY(0)
      rotateX(`,n(360),`deg)
      rotateY(`,n(360),`deg)
      rotateZ(`,n(360),"deg);}to{transform:translateY(calc(100vh + ",o,`px))
      rotateX(0)
      rotateY(0)
      rotateZ(0);}`),_=i("img",{target:"es7rdur0"})(({theme:t})=>({position:"fixed",top:`${-o}px`,marginLeft:`${-r/2}px`,zIndex:t.zIndices.balloons,left:`${n(S,E)}vw`,animationDelay:`${n(u)}ms`,height:`${o}px`,width:`${r}px`,pointerEvents:"none",animationDuration:"3000ms",animationName:x(),animationTimingFunction:"ease-in",animationDirection:"normal",animationIterationCount:1,opacity:1})),w=100,s=[d,f,g],I=s.length,M=({particleType:t})=>e(_,{src:s[t]}),h=function({scriptRunId:a}){return e(p,{children:e(l,{className:"stSnow","data-testid":"stSnow",scriptRunId:a,numParticleTypes:I,numParticles:w,ParticleComponent:M})})},P=c.memo(h);export{w as NUM_FLAKES,P as default};
