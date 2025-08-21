## Challenge Geneartion for Attack Defence CTF

This is the idea as follows which needs a little bit more refining:

### AcademyGram

We can bots that are ctf academy players. These bots need to post messages like instagram but like random messages. List of player username:
Gluncho
brightprogrammer
Saan
InkaDinka
CROWNPRINCE
Ze:R0
Alchemy1729
kobush
LE_THOG
AAAA
mistertoenails
emi
hs
hanto
RenegadePenguin
aturt13
Platinum
nendo
antiriad7
0xVul
razzledazzle
Leo
Snowy
thairog
x3ero0
k1R4
VessaX
Newtons4thLaw
rxgel
ordinary
NopNopGoose
amateurhour
SMCxDeathBurger
TUNISIA_ALBERT
ThatGuySteve
prosdkr
George
Gus
stevie
HackOlympus
Elvis
Shunt
slowman
Canlex
Flipout50
0xcosmos
beaver
xuesu
j88001
Tedan Vosin
HAL50000
cyx
Gh05t-1337
kaal
j3r3mias
/bin/cat
Jared
profl@¥
Sylvie
「」
nucko
Adical
Ron
fatalynk
F4_U57
A1.exe
0xFFFFFF
e-.
ch0mp4
Sammy 

As this is a attack defence ctf we need a checker which puts the flag according to the current tick like this github example- https://github.com/X3eRo0/academy-ctf-challenges/raw/refs/heads/master/cowsay/checker.py. Checker would login through the admin account and make the private post.

We are making a facebook like service:
https://www.malwarebytes.com/blog/news/2024/02/facebook-bug-could-have-allowed-attacker-to-take-over-accounts

Pick any Facebook account.
Try to login as that user and request a password reset (Forgot password).
From the available reset options choose “Send code via Facebook notification”.
This creates a POST request. As part of a POST request, an arbitrary amount of data of any type can be sent to the server in the body of the request message.
Copy that POST request and use a method to try all the 100,000 possibilities. Note, 100,000 possibilities may sound like a lot, but given the two hour time-frame there are plenty of options to do that.
The matching code responds with a 302 status code, a redirect that confirms the search was successful.
Use the correct code to reset the password of the account and the attacker can now take over the account.



#### Bugs 1:

The reset code does not expire for 30 mins and its only 4 digits for our service so anyone can bruteforce the code to get access to the admin account. We just code sent to the user's facebook account as a notification. 


#### Bug 2:
https://medium.com/@nvmeeet/4300-instagram-idor-bug-2022-5386cf492cad

User id can be changed to get access to interest page/ whatever to get the flag in form of a post of an account followed or a picture.


#### Bug 3:
Local file inclusion. ~~all the images path~


