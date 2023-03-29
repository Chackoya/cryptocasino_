from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from flash_bets.serializers import FlashBetSerializer

import time

from utils import flash_bets,provably_fair_dice,dice_setup
from core.models import FlashBet,Profile_User,Casino_Bankroll,Seed

class FlashBetViewSet(viewsets.ModelViewSet):
    queryset = FlashBet.objects.all()
    serializer_class = FlashBetSerializer
    
    
    #Following lines allow to specify that to use any of the ENDPOINTS from this view set:
    # a tokenauthentication type is required AND the user has to be authenticated; (error otherwise)
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]


    def get_queryset(self):
        """Retrieve trx flash hist for authenticated user."""
        return self.queryset.filter(user=self.request.user).order_by('-id') # Filtered by user & ordered by id 
    
    #@transaction.atomic
    @action(detail=False, methods=['post'], url_path='process')
    def process_flash_bet(self, request):
        serializer = FlashBetSerializer(data=request.data)
        
        
        print("USER:",self.request.user , "BETTING ")
        print()
        
        
        st = time.time()
        
        if serializer.is_valid():
            user = request.user            
            print(user)
            user = self.request.user
            
            print(user , "same:", request.user == self.request.user)
            #Get data from user; Such as his profile with coin balances and Seed; 
            res_profile = Profile_User.objects.filter(user_id=request.user).first()
            res_seed = Seed.objects.filter(user_id=request.user).first()
            casino_roll = Casino_Bankroll.objects.first() #Casino bankroll;
            

            #
            number_of_bets = serializer.validated_data['number_of_bets']
            bet_amount = serializer.validated_data["bet_amount"]
            
            #print("USER HERE:",user, request.user)
            
            
            #>Compute the roll with provably fair script
            #0) if bet is between 0.01 and 98% then proceed, else return response error ; => done in create method return custom response
            #1) Verify if user already has a server_seed that is not visible yet, if yes use that one otherwise create a new one.
            #2) Perform rolls on the combination of the client_seed & server_seed (and nonce) 
            #3) Compute dice params based on user inputs from request 
            #4) Compare rolls results and check if win or lose
            if res_seed.visible:
                pfair = provably_fair_dice.ProvablyFair() #use constructor that automatically generates new seed;
                res_seed.modify_server_seed(pfair.server_seed)
            else:
                pfair = provably_fair_dice.ProvablyFair(res_seed.server_seed)

            print("SEEDS", res_seed.client_seed, res_seed.server_seed)            
            #Compute the dice setup (payouts and min max ranges for the dice - for current bet)

            dice_params_current_bet = dice_setup.compute_dice_setup(serializer.validated_data["user_winrate_choice"], 
                                                                        serializer.validated_data["is_roll_under"])
                
            won_amount_after_fee = (serializer.validated_data["bet_amount"] * dice_params_current_bet.payout_X ) - serializer.validated_data["bet_amount"]#Value for Adding funds according in case user wins;
                
            winnings, losses = 0, 0
            net_profit=0
            for index_bet in range(number_of_bets):
                #Provably fair script;
                rolled_data = pfair.roll(res_seed.client_seed, res_seed.nonce)
                #print("ROLLED DATA TRX:",rolled_data.roll)
                try:
                    #Win bet if rolled dice from provably fair in within computed ranges
                    if dice_params_current_bet.min_range <= rolled_data.roll < dice_params_current_bet.max_range:
                        net_profit+=won_amount_after_fee #The user won the bet; so he gets a profit, with a reduction coming from fee
                        winnings+=1
                    else: #else lose and reduce funds from user
                        losses+=1
                        net_profit-= serializer.validated_data["bet_amount"] 
                except ValueError as e :
                    print("Error:",e)
                    if net_profit>0:
                        res_profile.gain_funds(amount =net_profit, coin_ticker = serializer.validated_data["coin_ticker"], casino_ref = casino_roll )
                    else:
                        res_profile.reduce_funds_bet( amount = -net_profit , coin_ticker = serializer.validated_data["coin_ticker"], casino_ref = casino_roll )
                    return Response({
                        'status': 'error',
                        'message': 'Insufficient funds, stopped at the bet number: '+str(index_bet),
                        
                        'winnings': winnings,
                        'losses': losses,
                        
                        'net_profit':net_profit,
                        'coin_ticker':serializer.validated_data["coin_ticker"],
                        
                    }, status=status.HTTP_400_BAD_REQUEST)
                #update user nonce for next bet with the same seed:
                res_seed.increment_nonce()
            

            # get the end time
            et = time.time()
            # get the execution time
            elapsed_time = et - st
            print('Execution time:', elapsed_time, 'seconds')
            # Save the FlashBet instance after processing all bets
            #flash_bet = FlashBet(user=self.request.user, number_of_bets=number_of_bets, bet_amount=bet_amount)
            #flash_bet.save()
            serializer.save(user=user, number_of_bets=number_of_bets, bet_amount=bet_amount)
            return Response({
                'status': 'success',
                'winnings': winnings,
                'losses': losses,
                'net_profit':net_profit,
                'coin_ticker':serializer.validated_data["coin_ticker"],
                'time_run':elapsed_time
            }, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

