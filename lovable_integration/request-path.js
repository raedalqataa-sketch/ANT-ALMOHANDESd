'use strict';
/* Match API requests locally even with query flags; never intercept another origin. */
(function(root){
 function requestPath(input,base){
  const url=new URL(typeof input==='string'?input:input.url,base);
  return url.origin===new URL(base).origin?url.pathname:url.href;
 }
 if(typeof module!=='undefined'&&module.exports)module.exports=requestPath;
 else root.AntRequestPath=requestPath;
})(typeof window==='undefined'?globalThis:window);
