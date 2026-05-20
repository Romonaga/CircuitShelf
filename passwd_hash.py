import bcrypt

password = b"covert69guess"
hashed = bcrypt.hashpw(password, bcrypt.gensalt())
print(hashed.decode())

