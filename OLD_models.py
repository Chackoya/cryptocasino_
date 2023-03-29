"""
Database models
"""
from django.conf import settings
from django.db import models,transaction
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
    )
from django.utils.timezone import now
import os
from dotenv import load_dotenv
from django.db.models.signals import post_save
from django.dispatch import receiver
from utils import utils_encryption
from secrets import token_hex

# Load the .env file
load_dotenv()
print()
SEEDS_KEYWORD =   os.environ['SEEDS_KEY']
"""
USER MODELS: profiles, logins 
"""
class UserManager(BaseUserManager):
    """Manager for users."""

    def create_user(self, email, password=None, **extra_fields):
        """Create, save and return a new user."""
        
        if not email:
            raise ValueError("User must have an email adress")
            
        user = self.model(email=self.normalize_email(email), **extra_fields) #using the User bellow basically
        user.set_password(password) #set a pass for the new created user; hashed 
        user.save(using=self._db) # save it to the db 

        return user
    
    def create_superuser(self, email, password):
        """Create and return a new superuser."""
        user = self.create_user(email, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)

        return user


#AbstractBaseUser : functionaly for auth system (have to create fields)
#PermissionsMixin : func for permissions & fields
class User(AbstractBaseUser, PermissionsMixin):
    """User in the system."""
    email = models.EmailField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
   

###############################################################################
"""
GAME MODELS: bets ingame (historic) & seeds for provably fair games
"""

class Bet_Model(models.Model):
    """ Basic model for a bet on dice game"""
    type_game=models.CharField(max_length=20,default="DICE") #DICE for example
    user_winrate_choice = models.DecimalField('User_Choice_Winrate', max_digits=5,decimal_places=2 , default=0) 
    is_roll_under = models.BooleanField(default=True)

    date_game = models.DateTimeField('Date_Play', default=now)
    bet_amount = models.DecimalField('Bet_Amount',max_digits=18, decimal_places=8,default=0) #monetary apps might not use this type 'Decimal' 
    coin_ticker = models.CharField('Coin_Ticker', max_length=20 ,default='COIN') 
    payout_multiplier = models.DecimalField('User_Choice_Roll', max_digits=8,decimal_places=5 , default=0) 

    description = models.TextField(blank=True) #Textfield => more content but also slower than charfield
    
    class Meta:
        abstract = True
    
#Class for the transactions model (historic of a game)
class Game_Trx_historic(Bet_Model):
    """Game-Transaction historic Model: represent unique bets on the dice. """
    #user relationship with trxs => each transaction history belongs to a user;
    user = models.ForeignKey( 
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    
    
    rolled_dice = models.DecimalField('Result_Dice_Roll', max_digits=5,decimal_places=2 , default=0) #ROLLED VALUE WITH PROVABLY FAIR STEPS;
    #payout_multiplier = models.DecimalField('User_Choice_Roll', max_digits=8,decimal_places=5 , default=0) 
    is_winner = models.BooleanField(default=False)


    def __str__(self):
        return self.description
#Class for Custom Dice Strategies saved by user
class Dice_Custom_Strategies(Bet_Model):
    """Represent saved strats for each user"""
        
    user = models.ForeignKey( 
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    title_strategy = models.CharField('Title_Strategy', max_length=50 ,default='Strat') 
    number_of_rolls =  models.PositiveIntegerField(default=0)
    #TODO
    #Missing extra configuration rules (on win, on loss resets for example)...

class FlashBet(Bet_Model):
    user = models.ForeignKey( 
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    
    number_of_bets = models.PositiveIntegerField()


from hashlib import sha256, sha512
#Class seed for Provably fair part
class Seed(models.Model):
    """Represent seed for provably random number generation. 
    
    Each  store
    its char value and specify if seed is visible or not, this
    property is established depending on whether it is still in use.
    """
        
    user = models.OneToOneField(User, on_delete=models.CASCADE) #One to one field due to the fact that a user can only have a sigle SEED setup
    client_seed = models.CharField(max_length=300,default="Seed") #Based on input from user or random elements from him;
    server_seed = models.CharField(max_length=300,default= "ServerSeed")#token_hex(32))
    hashed_server_seed_for_user = models.CharField(max_length=300,default="HASH")
    visible = models.BooleanField(default=False) #If the server seed is visible/revealed by user already
    nonce = models.PositiveIntegerField(default=0)
    
    

    
    def __str__(self):
        """Show seed of visible object and 'Hidden' for unvisible ones."""
        if self.visible is True:
            return self.server_seed
        else:
            return 'Hidden'

    def increment_nonce(self):
        self.nonce += 1
        self.save(update_fields=['nonce'])
    
    def modify_server_seed(self, new_ss=None):
        if new_ss != None:
            self.server_seed = new_ss 
        else:
            self.server_seed = token_hex(32)
            
            
        #hash it before:
        self.hashed_server_seed_for_user = utils_encryption.hash_input_SHA256(self.server_seed)#self.hash_it_without_decrypt()
        #encrypt server_seed:
        self.server_seed = utils_encryption.encrypt(self.server_seed, SEEDS_KEYWORD)
        self.visible = False
        self.nonce = 0 #Reset nonce
        self.save(update_fields=['server_seed','visible','nonce','hashed_server_seed_for_user'])
        
    def modify_client_seed(self,new_cs):
        self.client_seed = new_cs 
        self.save(update_fields=['client_seed'])
        
    def decrypt_server_seed(self):
        print("uhzeuhzeu",SEEDS_KEYWORD, self.server_seed)
        print()
        return  utils_encryption.decrypt(self.server_seed, SEEDS_KEYWORD)
    
    def reveal_server_seed(self):
        
        original_seed = self.decrypt_server_seed()
        self.visible = True 
        self.save(update_fields=['visible'])
    
        return original_seed
    
    #def init_server_seed(self) :
    #    """ Initialize starting server seed when user is created and their profile """
    #    self.server_seed = token_hex(32)
    def hash_server_seed(self):
        """Get the hash of the server _seed (original)
        1- We have to decrypt the seed stored in the DB ; 
        2 - Hash it and return (this is what we show to the user until he reveals the server seed )
        """
        original_seed = self.decrypt_server_seed()
        #server_seed_hash_object = sha256(self.server_seed.encode())
        server_seed_hash_object = sha256(original_seed.encode())
        server_seed_hash = server_seed_hash_object.hexdigest()
        
        return server_seed_hash

#Create a matching entry in SEED Table everytime a user is created
@receiver(post_save, sender=User)
def update_seed_signal(sender, instance, created, **kwargs):
    if created:
        s = Seed.objects.create(user=instance)
        tmp_server_seed = token_hex(32)
        #print("S:,",s.server_seed)
        hashed_field = utils_encryption.hash_input_SHA256(tmp_server_seed)
        s.hashed_server_seed_for_user = hashed_field
        s.server_seed = utils_encryption.encrypt(tmp_server_seed, SEEDS_KEYWORD)
        s.save(update_fields=['hashed_server_seed_for_user','server_seed'])
                
    #instance.profile.save()




#-----------------------------------------------------------------------------#

###############################################################################
"""
PROFILES: keep track of funds for each blockchain & currencies & Settings
"""

class Account_balances(models.Model):
    PLAY_amount = models.DecimalField('AmountPLAY', max_digits=18, decimal_places=8, default=100)
    ETH_amount = models.DecimalField('AmountBTC', max_digits=18, decimal_places=8, default=0)
    BTC_amount = models.DecimalField('AmountETH', max_digits=18, decimal_places=8, default=0)

    class Meta:
        abstract = True



#CASINO BANKROLL ACCOUNT; 
class Casino_Bankroll(Account_balances):
    is_bank_acc = models.BooleanField(default=True)
    label = models.CharField('Label', max_length=100 ,default='Bankroll')  # Ticker
    
#INNER ACCOUNT BALANCES MODEL: https://github.com/limpbrains/django-cc/blob/master/cc/models.py
class Profile_User(Account_balances):
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    @transaction.atomic()
    def reduce_funds_bet(self, amount ,coin_ticker , casino_ref):
        """ Check for sufficient funds for the user and reduce the amount of funds available based on the bet size for the specific coin"""
        
        
        if amount < 0:
            raise ValueError('Invalid Amount')
        #Check for tickers (valid used coin):
        if coin_ticker=="ETH":
            if self.ETH_amount - amount < 0 :
                raise ValueError('Not enough funds')
            
            else:
                self.ETH_amount -= amount
                self.save()
                casino_ref.ETH_amount +=amount
                casino_ref.save()
        ######################
        elif coin_ticker=="BTC":
            if self.BTC_amount - amount < 0 :
                raise ValueError('Not enough funds')
            
            else:
                self.BTC_amount -= amount
                self.save()
                casino_ref.BTC_amount +=amount
                casino_ref.save()
        ######################
        elif coin_ticker=="PLAY":
            if self.PLAY_amount - amount < 0 :
                raise ValueError('Not enough funds')
            
            else:
                self.PLAY_amount -= amount
                self.save()
                casino_ref.PLAY_amount +=amount
                casino_ref.save()
        ######################
        else:
            raise ValueError('Bad ticker for bet')
    
    
    @transaction.atomic()
    def gain_funds(self, amount,coin_ticker , casino_ref): 
        """ USER WON BET; INCREASE COIN AMOUNT (ticker) AND REDUCE THE CASINO ACCOUNT VALUES"""
        if coin_ticker=="ETH":
                self.ETH_amount += amount
                self.save()
                casino_ref.ETH_amount -=amount
                casino_ref.save()
        ######################
        elif coin_ticker=="BTC":
                self.BTC_amount += amount
                self.save()
                casino_ref.BTC_amount -=amount
                casino_ref.save()
        ######################
        elif coin_ticker=="PLAY":
                self.PLAY_amount += amount
                self.save()       
                casino_ref.PLAY_amount -=amount
                casino_ref.save()
        else:
            raise ValueError('Bad ticker for bet')
    
    @transaction.atomic()
    def deposit_funds_wallet (self, amount,coin_ticker):
        if coin_ticker=="ETH":
                self.ETH_amount += amount
                self.save()
        ######################
        elif coin_ticker=="BTC":
                self.BTC_amount += amount
                self.save()
        ######################
        elif coin_ticker=="PLAY":
                self.PLAY_amount += amount
                self.save()       
        else:
            raise ValueError('Bad ticker for bet')
            
    def __str__(self):
        return f'{self.user.name} Profile and balances'


#Create a matching entry in PROFILE_USER Table everytime a user is created
@receiver(post_save, sender=User)
def update_profile_signal(sender, instance, created, **kwargs):
    if created:
        Profile_User.objects.create(user=instance)
    #instance.profile.save()





###############################################################################
"""
WALLETS MODELS: for assignment of wallets to a user & model for each user deposit/withdraws
"""

class Wallet(models.Model):
    """ Wallet in the system (basemodel)."""
    public_key = models.CharField('Public', max_length=50) #Address public acc
    private_key = models.CharField( 'Private',  max_length=255) #private key to keep secret & encrypted.
    
    blockchain = models.CharField('Blockchain',max_length=20)
    generated_at = models.DateTimeField('Date_Created',auto_now_add=True)

    #USER / OWNER OF THIS DEPOSIT ADDRESS ;
    user = models.ForeignKey( 
        settings.AUTH_USER_MODEL,#AUTH_USER_MODEL defined in our settings.py file => avoid hardcoded refs 
        on_delete=models.CASCADE,#in case we delete the user; it will also cascade and delete all the transactions of the games he played;
        #At the start there is no assignement;
        blank=True,
        null=True
    )
    assigned_to_user_date = models.DateTimeField('Date_Assigned',auto_now=True)
    value_amount = models.DecimalField('Amount', max_digits=18, decimal_places=8, default=0) #models.DecimalField(max_digits=6, decimal_places=5) 
    counter_deposits = models.PositiveIntegerField(default=0) #Number of deposits (unique) made to this wallet;
    def __str__(self):
        return str(self.public_key)#"User " + str(self.user.name) + " is assigned the adress: " + str(self.public_key) +" for blockchain" + str(self.blockchain)
    
    
    
    
    
class User_Deposit(models.Model):
    """Represent single money deposit made by user using casino.

    Define fields to store amount of money, using Decimal field with
    two places precision and maximal six digits, time of deposit creation,
    and connect every deposit with user and used currency.
    """
    deposit_time = models.DateTimeField('DateDepositCasino',auto_now=True)
    #date_trx_block = models.DateTimeField('DateBlock',auto_now=True)
    unique_trx_hash =  models.CharField('Transaction_Hash',max_length=125) #Unique transaction hash from the blockchain;
    blockchain = models.CharField('Blockchain',max_length=20) #blockchain used to deposit;
    coin_ticker = models.CharField('Coin_Ticker', max_length=20 ,default='COIN') 
    amount = models.DecimalField(max_digits=18, decimal_places=8)
    
    #Source address from this blockchain trx
    from_addy = models.CharField('Source_Address', max_length=50, null=True) 
    #Destination address of the deposit; foreignkey with user & wallet models
    to_addy = models.ForeignKey(Wallet, on_delete=models.CASCADE, null=True)
    user_id = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    """
    currency_id = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
    )
    """
    def __str__(self):
        """Simply present name of user connected with deposit and amount."""
        return self.user_id.name + " made " + str(self.amount) + " deposit of "+ self.coin_ticker





class User_Withdraw(models.Model):
    """Represent user's willingness to withdraw money.

    Define fields to store amount of money, using Decimal field with
    two places precision and maximal six digits, time when withdraw will
    was signaled and connect every withdraw with user and used currency.
    """

    amount = models.DecimalField(max_digits=6, decimal_places=2)
    address = models.CharField(max_length=100)
    withdraw_time = models.DateTimeField()
    user_id = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    """
    currency_id = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
    )
    """
    def __str__(self):
        """Simply present name of user connected with withdraw and amount."""
        return self.user_id.name + " wants to withdraw " + str(self.amount)




"""
UTILS METHODS
"""
#TODO UTILS METHODS:##########################################################################################################################################
from django.core.exceptions import ValidationError
from django.db import IntegrityError, DatabaseError, transaction

def save_model_instance(instance , updatefields=None):
    try:
        # Wrap the save operation in an atomic transaction to ensure data consistency
        with transaction.atomic():
            if updatefields!=None:
                instance.save(update_fields=updatefields)
            else:
                instance.save()
                
    except ValidationError as ve:
        # Handle validation errors
        print("Validation error occurred:", ve)
        # You can return the error or raise a custom exception here
    except IntegrityError as ie:
        # Handle integrity errors, like unique constraints violations
        print("Integrity error occurred:", ie)
        # You can return the error or raise a custom exception here
    except DatabaseError as de:
        # Handle general database errors
        print("Database error occurred:", de)
        # You can return the error or raise a custom exception here
    except Exception as e:
        # Handle any other unexpected exceptions
        print("Unexpected error occurred:", e)
        # You can return the error or raise a custom exception here
    else:
        print("Model saved successfully.")
        return instance
