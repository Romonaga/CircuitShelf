SELECT pgp_sym_decrypt(decode(%s, 'base64'), %s) = %s AS matches;
