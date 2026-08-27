/* =========================================================
   NEXA WEB — service worker
   Guarda o site no aparelho e mostra a página de aviso
   quando a pessoa abre sem internet.
   ========================================================= */

const VERSAO = 'nexa-web-v1';
const PAGINA_OFFLINE = './404.html';

// o que fica guardado já na primeira visita
const ESSENCIAIS = [
  './',
  './index.html',
  './404.html'
];

// endereços que nunca devem ser guardados (dados que mudam o tempo todo)
const NUNCA_GUARDAR = [
  'supabase.co',
  'ntfy.sh',
  'wa.me',
  'api.whatsapp.com'
];

function ehDinamico(url){
  return NUNCA_GUARDAR.some(dominio => url.includes(dominio));
}

/* ---------- instalação: guarda o essencial ---------- */
self.addEventListener('install', (evento)=>{
  evento.waitUntil(
    caches.open(VERSAO)
      .then(cache => cache.addAll(ESSENCIAIS))
      .catch(()=>{})           // se algum arquivo falhar, instala do mesmo jeito
      .then(()=> self.skipWaiting())
  );
});

/* ---------- ativação: apaga versões antigas ---------- */
self.addEventListener('activate', (evento)=>{
  evento.waitUntil(
    caches.keys()
      .then(nomes => Promise.all(
        nomes.filter(n => n !== VERSAO).map(n => caches.delete(n))
      ))
      .then(()=> self.clients.claim())
  );
});

/* ---------- cada pedido do navegador ---------- */
self.addEventListener('fetch', (evento)=>{
  const req = evento.request;

  // só cuida de leitura; envio de formulário e afins passam direto
  if(req.method !== 'GET') return;
  if(ehDinamico(req.url)) return;

  // abrir uma página: sem internet, mostra o aviso na hora
  if(req.mode === 'navigate'){
    if(self.navigator && self.navigator.onLine === false){
      evento.respondWith(
        caches.match(PAGINA_OFFLINE)
          .then(r => r || caches.match('./index.html'))
          .then(r => r || fetch(req))
      );
      return;
    }
    // no-store: ignora o cache do navegador e testa a internet de verdade
    evento.respondWith(
      fetch(req, { cache: 'no-store' })
        .then(resposta => {
          const copia = resposta.clone();
          caches.open(VERSAO).then(cache => cache.put(req, copia)).catch(()=>{});
          return resposta;
        })
        .catch(()=> caches.match(PAGINA_OFFLINE).then(r => r || caches.match('./index.html')))
    );
    return;
  }

  // arquivos do site: entrega o guardado na hora e atualiza por trás
  evento.respondWith(
    caches.match(req).then(guardado => {
      const daRede = fetch(req)
        .then(resposta => {
          if(resposta && (resposta.ok || resposta.type === 'opaque')){
            const copia = resposta.clone();
            caches.open(VERSAO).then(cache => cache.put(req, copia)).catch(()=>{});
          }
          return resposta;
        })
        .catch(()=> guardado);
      return guardado || daRede;
    })
  );
});

/* ---------- permite atualizar sem fechar a aba ---------- */
self.addEventListener('message', (evento)=>{
  if(evento.data === 'atualizar-agora') self.skipWaiting();
});
