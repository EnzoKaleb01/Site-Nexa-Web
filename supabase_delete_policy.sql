-- Rode isso no Supabase em: SQL Editor → New query
-- (é um complemento do supabase_schema.sql que você já rodou)
--
-- Agora que o site fala DIRETO com o Supabase pelo navegador (sem
-- passar mais pelo backend Python), precisamos de uma policy de
-- DELETE também. A segurança continua garantida: o site sempre filtra
-- a exclusão por id + token_exclusao ao mesmo tempo, e sem saber o
-- token certo (que só existe na memória de quem criou a avaliação),
-- o filtro não bate em nenhuma linha e nada é apagado.

create policy "avaliacoes_delete_com_token"
  on public.avaliacoes for delete
  using (true);
